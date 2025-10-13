"""
Utilitários gerais.
"""

from .file_utils import (
    read_text, normalize_rel, iter_source_files, 
    find_xcode_project_root, should_ignore_path
)
from .cache_manager import CacheManager
from .config_manager import ConfigManager

__all__ = [
    'read_text', 'normalize_rel', 'iter_source_files',
    'find_xcode_project_root', 'should_ignore_path',
    'CacheManager', 'ConfigManager'
]