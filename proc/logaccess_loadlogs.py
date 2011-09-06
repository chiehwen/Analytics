#!/usr/bin/env python
from logaccess_config import *
import apachelog
from pymongo import Connection 
import sys
import os
import re
#from lib.ip2country.ip2country import IP2Country
from datetime import date
from urlparse import urlparse


def validate_pid(script, pid):
    validate = False
    
    if script == "sci_issuetoc":
        if re.search(REGEX_ISSUE,pid):
            return True
    elif script == "sci_abstract" or re.search(REGEX_FBPE,pid):
        if re.search(REGEX_ARTICLE,pid):
            return True
    elif script == "sci_arttext":
        if re.search(REGEX_ARTICLE,pid) or re.search(REGEX_FBPE,pid):
            return True
    elif script == "sci_pdf":
        if re.search(REGEX_ARTICLE,pid) or re.search(REGEX_FBPE,pid):
            return True
    elif script == "sci_serial":
        if re.search(REGEX_ISSN,pid):
            return True
    elif script == "sci_issues":
        if re.search(REGEX_ISSN,pid):
            return True
        
    return False


conn = Connection('localhost', 27017)

db = conn.accesslog
proc_files = db.processed_files
error_log = db.error_log
analytics = db.analytics
analytics.ensure_index('site')
analytics.ensure_index('serial')
analytics.ensure_index('issuetoc')
analytics.ensure_index('arttext')
analytics.ensure_index('abstract')
analytics.ensure_index('pdf')
analytics.ensure_index('page')
analytics.ensure_index('issn')
analytics.ensure_index('issue')
error_log.ensure_index('file')

print "listing log files at: "+LOGS_DIR

logfiles = os.listdir(LOGS_DIR)

for file in logfiles:
    fileloaded = open(LOGS_DIR+"/"+file, 'r')
    if proc_files.find({'_id':file}).count() == 0:
        lines = 0
        lines = os.popen('cat '+LOGS_DIR+"/"+file+' | wc -l').read().strip()
        proc_files.update({"_id":file},{'$set':{'proc_date':date.isoformat(date.today()),'status':'processing','lines': lines}},True)
        print "processing "+file
        count=0
        linecount=0
        for line in fileloaded:
            linecount=linecount+1
            proc_files.update({"_id":file},{'$set':{'line':linecount}},True)
            if "GET /scielo.php?script=" in line:
                count=count+1
                p = apachelog.parser(APACHE_LOG_FORMAT)
                try:
                    data = p.parse(line)
                except:
                    sys.stderr.write("Unable to parse %s" % line)

                if MONTH_DICT.has_key(data['%t'][4:7].upper()):
                    month = MONTH_DICT[data['%t'][4:7].upper()]
                else:
                    continue
                
                dat = data['%t'][8:12]+month
                url = data['%r'].split(' ')[1]
                ip = data['%h']
                
                #i2pc = IP2Country(verbose=False)
                #cc, country = i2pc.lookup(ip)
                #country = "country_"+str(cc)
                #print str(cc)+" "+ip
                
                params = urlparse(url).query.split('&')
                par = {}
                
                for param in params:
                    tmp = param.split('=')
                    if len(tmp) == 2:
                        par[tmp[0]] = tmp[1]
                par['date'] = dat
                #print par
                language = ""
                if par.has_key('tlng'):
                    if par['tlng'].upper() in ALLOWED_LANGUAGES:
                        language=par['tlng'].lower()
                    else:
                        language='default'
                else:
                    language='default'
                    
                if par.has_key('script'):
                    
                    script = par['script'].upper()
                    
                    if par['script'].upper() in ALLOWED_SCRIPTS:
                        script=par['script'].lower()
                        analytics.update({"site":"www.scielo.br"}, {"$inc":{script:1,'total':1,"dat_"+par['date']:1}},True)
                        if par.has_key('pid'):
                            pid = par['pid'].replace('S','').replace('s','').strip()
                            if validate_pid(script,pid):
                                # CREATING SERIAL LOG DOCS
                                analytics.update({"serial":str(pid).replace('S','')[0:9]}, {"$inc":{'total':1,script:1,par['date']:1,'lng_'+par['date']+'_'+language:1}},True)
                                if script == "sci_issuetoc":
                                    analytics.update({"issuetoc":pid}, {"$set":{'page':script,'issn':pid[0:9]},"$inc":{'total':1,"dat_"+par['date']:1}},True)
                                elif script == "sci_abstract":
                                    analytics.update({"abstract":pid}, {"$set":{'page':script,'issn':pid[1:10],'issue':pid[1:18]},"$inc":{'total':1,"dat_"+par['date']:1,'lng_'+par['date']+'_'+language:1}},True)
                                elif script == "sci_arttext":
                                    analytics.update({"arttext":pid}, {"$set":{'page':script,'issn':pid[1:10],'issue':pid[1:18]},"$inc":{'total':1,"dat_"+par['date']:1,'lng_'+par['date']+'_'+language:1}},True)
                                    analytics.update({"site":"www.scielo.br"}, {"$inc":{"art_"+par['date']:1,'art_'+par['date']+'_'+language:1}},True)
                                elif script == "sci_pdf":
                                    analytics.update({"pdf":pid}, {"$set":{'page':script,'issn':pid[1:10],'issue':pid[1:18]},"$inc":{'total':1,"dat_"+par['date']:1,'lng_'+par['date']+'_'+language:1}},True)
                                    analytics.update({"site":"www.scielo.br"}, {"$inc":{"pdf_"+par['date']:1,'pdf_'+par['date']+'_'+language:1}},True)
                            else:
                                print str(validate_pid(script,pid))+" "+script+" "+pid
                                analytics.update({"site":"www.scielo.br"}, {"$inc":{'err_total':1,'err_pid':1}},True)
                                error_log.update({"file":file},{"$set":{'lines':lines},"$inc":{'err_pid':1}},True)
                        else:
                            analytics.update({"site":"www.scielo.br"}, {"$inc":{'err_total':1,'err_empty_pid':1}},True)
                            error_log.update({"file":file},{"$set":{'lines':lines},"$inc":{'err_empty_pid':1}},True)                            
                    else:
                        analytics.update({"site":"www.scielo.br"},{"$inc":{'err_total':1,'err_script':1}},True)
                        error_log.update({"file":file},{"$set":{'lines':lines},"$inc":{'err_script':1}},True)
                else:
                    analytics.update({"site":"www.scielo.br"}, {"$inc":{'err_total':1,'err_empty_script':1}},True)
                    error_log.update({"file":file},{"$set":{'lines':lines},"$inc":{'err_empty_script':1}},True)
        proc_files.update({"_id":file},{'$set':{'status':'processed'}},True)
    else:
        print file+" was already processed"