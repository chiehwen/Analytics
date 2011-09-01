from pyramid.config import Configurator
from analystics.resources import Root

def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    config = Configurator(root_factory=Root, settings=settings)
    config.add_view('analystics.views.chat_site',
                    context='analystics:resources.Root',
                    renderer='analystics:templates/chat_site.pt')
    config.add_static_view('static', 'analystics:static')
    return config.make_wsgi_app()