"""
Parser para arquivos Objective-C e Objective-C++.
"""

import re
from typing import Set, Tuple
from .base_parser import BaseParser
from ..constants import COMMON_KEYWORDS


class ObjCParser(BaseParser):
    """
    Parser especializado para Objective-C/Objective-C++.
    """
    
    def setup_patterns(self):
        """
        Configura padrões regex para Objective-C.
        """
        # Padrões para declarações
        self.re_interface = re.compile(r'@interface\s+([A-Za-z_]\w*)')
        self.re_protocol = re.compile(r'@protocol\s+([A-Za-z_]\w*)')
        self.re_implementation = re.compile(r'@implementation\s+([A-Za-z_]\w*)')
        self.re_category = re.compile(r'@interface\s+([A-Za-z_]\w*)\s*\(([A-Za-z_]\w*)\)')
        self.re_enum = re.compile(r'typedef\s+NS_ENUM\s*\([^,]+,\s*([A-Za-z_]\w*)\)')
        self.re_c_function = re.compile(
            r'^(?:static\s+)?(?:inline\s+)?(?:extern\s+)?[A-Za-z_]\w*\s+\*?\s*([A-Za-z_]\w*)\s*\(', 
            re.MULTILINE
        )
        
        # Padrões para imports
        self.re_import_local = re.compile(r'#\s*import\s*"([^"]+)"')
        self.re_include_local = re.compile(r'#\s*include\s*"([^"]+)"')
        self.re_import_module = re.compile(r'@import\s+([A-Za-z_][\w\.]*)\s*;')
        
        # Padrões para uso de símbolos
        self.re_class_forward = re.compile(r'@class\s+([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*;')
        self.re_msg_send_class = re.compile(r'\[\s*([A-Z][A-Za-z_]\w*)\s+([A-Za-z_]\w*)')
        self.re_msg_send_obj = re.compile(r'\[\s*([a-z_][A-Za-z_]\w*)\s+([A-Za-z_]\w*)')
        self.re_type_usage = re.compile(r'\b([A-Z][A-Za-z_]\w*)\s*\*')
        self.re_protocol_use = re.compile(r'id\s*<\s*([A-Za-z_]\w*)\s*>')
        self.re_c_func_call = re.compile(
            r'\b(NS[A-Z]\w*|CF[A-Z]\w*|CG[A-Z]\w*|UI[A-Z]\w*|dispatch_\w+|pthread_\w+)\s*\('
        )
    
    def extract_declarations(self, content: str, file_path: str) -> Set[str]:
        """
        Extrai declarações de classes, protocolos, etc. de código Objective-C.
        """
        declarations = set()
        
        # Classes
        for match in self.re_interface.findall(content):
            declarations.add(match)
        
        # Protocolos
        for match in self.re_protocol.findall(content):
            declarations.add(match)
        
        # Implementações
        for match in self.re_implementation.findall(content):
            declarations.add(match)
        
        # Categorias
        for cls, cat in self.re_category.findall(content):
            declarations.add(f'{cls}({cat})')
        
        # Enums
        for match in self.re_enum.findall(content):
            declarations.add(match)
        
        # Funções C
        for match in self.re_c_function.findall(content):
            if self.is_valid_symbol(match, COMMON_KEYWORDS):
                declarations.add(match)
        
        return declarations
    
    def extract_imports(self, content: str) -> Set[str]:
        """
        Extrai imports e includes de código Objective-C.
        """
        imports = set()
        
        # Imports locais
        for match in self.re_import_local.findall(content):
            imports.add(match)
        
        # Includes locais
        for match in self.re_include_local.findall(content):
            imports.add(match)
        
        # @import de módulos
        for match in self.re_import_module.findall(content):
            imports.add(f'@module:{match}')
        
        return imports
    
    def extract_symbol_usage(self, content: str) -> Set[Tuple[str, str]]:
        """
        Extrai uso de símbolos de código Objective-C.
        """
        uses = set()
        
        # Remove comentários para análise
        clean_content = self.remove_comments(content)
        
        # Forward declarations
        for line in self.re_class_forward.findall(content):
            for sym in [s.strip() for s in line.split(',')]:
                if self.is_valid_symbol(sym, COMMON_KEYWORDS):
                    uses.add((sym, 'type'))
        
        # Message sends para classes
        for cls, selector in self.re_msg_send_class.findall(clean_content):
            if self.is_valid_symbol(cls, COMMON_KEYWORDS):
                uses.add((cls, 'type'))
                if self.is_valid_symbol(selector, COMMON_KEYWORDS):
                    uses.add((f'{cls}.{selector}', 'call'))
        
        # Message sends para objetos
        for obj, selector in self.re_msg_send_obj.findall(clean_content):
            if self.is_valid_symbol(selector, COMMON_KEYWORDS) and len(selector) > 4:
                if not selector.startswith('set') and not selector.startswith('get'):
                    uses.add((selector, 'call'))
        
        # Uso de tipos
        for type_name in self.re_type_usage.findall(clean_content):
            if (self.is_valid_symbol(type_name, COMMON_KEYWORDS) and 
                not type_name.startswith('NS') and 
                not type_name.startswith('UI')):
                uses.add((type_name, 'type'))
        
        # Uso de protocolos
        for proto in self.re_protocol_use.findall(clean_content):
            if self.is_valid_symbol(proto, COMMON_KEYWORDS):
                uses.add((proto, 'proto'))
        
        # Chamadas de funções C
        for func in self.re_c_func_call.findall(clean_content):
            uses.add((func, 'func'))
        
        return uses