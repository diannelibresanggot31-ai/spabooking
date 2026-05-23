from django.core.management.commands.runserver import Command as BaseRunServerCommand
import logging

# Suppress the broken pipe errors in development
logging.getLogger('werkzeug').setLevel(logging.ERROR)

class Command(BaseRunServerCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--nothreading',
            action='store_true',
            dest='nothreading',
            help='Disable threading in the development server.',
        )
    
    def handle(self, *args, **options):
        # Suppress broken pipe errors by patching the logger
        import sys
        
        # Capture and suppress broken pipe errors
        original_excepthook = sys.excepthook
        
        def suppress_broken_pipe(exc_type, exc_value, traceback):
            import errno
            if exc_type.__name__ == 'BrokenPipeError' or (hasattr(exc_value, 'errno') and exc_value.errno == errno.EPIPE):
                return
            return original_excepthook(exc_type, exc_value, traceback)
        
        sys.excepthook = suppress_broken_pipe
        
        return super().handle(*args, **options)
