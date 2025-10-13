"""
Parser para arquivos Swift.
"""

import re
from typing import Set, Tuple
from .base_parser import BaseParser
from ..constants import COMMON_KEYWORDS, SWIFT_BASIC_TYPES, SWIFT_COMMON_PROTOCOLS


class SwiftParser(BaseParser):
    """
    Parser especializado para Swift.
    """
    
    def setup_patterns(self):
        """
        Configura padrões regex para Swift.
        """
        # Padrões para declarações
        self.re_type = re.compile(r'\b(class|struct|enum|protocol)\s+([A-Za-z_]\w*)')
        self.re_extension = re.compile(r'\bextension\s+([A-Za-z_]\w*)')
        self.re_func_top = re.compile(r'^\s*func\s+([A-Za-z_]\w*)\s*\(', re.MULTILINE)
        
        # Padrões para imports
        self.re_import = re.compile(r'^\s*import\s+([A-Za-z_][\w\.]*)', re.MULTILINE)
        
        # Padrões para uso de símbolos
        self.re_static_call = re.compile(r'\b([A-Z][A-Za-z_]\w*)\s*\.\s*([A-Za-z_]\w*)\s*\(')
        self.re_inst_call = re.compile(r'\b([a-z_][A-Za-z_]\w*)\s*\.\s*([A-Za-z_]\w*)\s*\(')
        self.re_type_annotation = re.compile(r':\s*([A-Z][A-Za-z_]\w*)')
        self.re_protocol_conformance = re.compile(
            r':\s*([A-Z][A-Za-z_]\w*)(?:\s*,|\s*{|\s*where|\s*$)'
        )
    
    def extract_declarations(self, content: str, file_path: str) -> Set[str]:
        """
        Extrai declarações de tipos e funções de código Swift.
        """
        declarations = set()
        
        # Tipos (class, struct, enum, protocol)
        for kind, name in self.re_type.findall(content):
            declarations.add(name)
        
        # Extensions (marcadas para diferenciação)
        for name in self.re_extension.findall(content):
            declarations.add(f'extension:{name}')
        
        # Funções top-level
        for func in self.re_func_top.findall(content):
            if self.is_valid_symbol(func, COMMON_KEYWORDS):
                declarations.add(func)
        
        return declarations
    
    def extract_imports(self, content: str) -> Set[str]:
        """
        Extrai imports de código Swift.
        """
        imports = set()
        
        for module in self.re_import.findall(content):
            imports.add(f'module:{module}')
        
        return imports
    
    def extract_symbol_usage(self, content: str) -> Set[Tuple[str, str]]:
        """
        Extrai uso de símbolos de código Swift.
        """
        uses = set()
        
        # Remove comentários para análise
        clean_content = self.remove_comments(content)
        
        # Chamadas estáticas (Type.method)
        for type_name, method in self.re_static_call.findall(clean_content):
            if self.is_valid_symbol(type_name, COMMON_KEYWORDS):
                uses.add((type_name, 'type'))
                if self.is_valid_symbol(method, COMMON_KEYWORDS):
                    uses.add((f'{type_name}.{method}', 'call'))
        
        # Chamadas de instância
        for obj, method in self.re_inst_call.findall(clean_content):
            if (self.is_valid_symbol(method, COMMON_KEYWORDS) and 
                len(method) > 4 and 
                not method.startswith('set') and 
                not method.startswith('get')):
                uses.add((method, 'call'))
        
        # Anotações de tipo
        for type_name in self.re_type_annotation.findall(clean_content):
            if (self.is_valid_symbol(type_name, COMMON_KEYWORDS) and 
                type_name not in SWIFT_BASIC_TYPES):
                uses.add((type_name, 'type'))
        
        # Conformidade a protocolos
        for proto in self.re_protocol_conformance.findall(clean_content):
            if (self.is_valid_symbol(proto, COMMON_KEYWORDS) and 
                proto not in SWIFT_COMMON_PROTOCOLS):
                uses.add((proto, 'proto'))
        
        return uses