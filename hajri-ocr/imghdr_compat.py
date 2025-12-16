"""
Python 3.13 compatibility fix for PaddleOCR
The imghdr module was removed in Python 3.13
"""
import sys

# Create a minimal imghdr module for compatibility
class ImghdrCompat:
    @staticmethod
    def what(file, h=None):
        """Determine image type (minimal implementation)"""
        if h is None:
            if hasattr(file, 'read'):
                h = file.read(32)
                file.seek(0)
            else:
                with open(file, 'rb') as f:
                    h = f.read(32)
        
        # Check common image formats
        if h.startswith(b'\xff\xd8\xff'):
            return 'jpeg'
        elif h.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'png'
        elif h.startswith(b'GIF'):
            return 'gif'
        elif h.startswith(b'BM'):
            return 'bmp'
        elif h.startswith(b'RIFF') and h[8:12] == b'WEBP':
            return 'webp'
        return None

# Inject into sys.modules
sys.modules['imghdr'] = ImghdrCompat()
