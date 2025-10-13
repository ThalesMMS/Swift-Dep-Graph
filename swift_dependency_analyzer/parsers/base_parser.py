"""
Parser base abstrato para análise de código fonte.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Set, Tuple, Dict, List
import re


class BaseParser(ABC):
    """
    Classe abstrata base para parsers de linguagem.
    """
    
    def __init__(self):
        self.setup_patterns()
    
    @abstractmethod
    def setup_patterns(self):
        """
        Configura os padrões regex específicos da linguagem.
        """
        pass
    
    @abstractmethod
    def extract_declarations(self, content: str, file_path: str) -> Set[str]:
        """
        Extrai declarações (classes, protocolos, etc.) do conteúdo do arquivo.
        
        Args:
            content: Conteúdo do arquivo
            file_path: Caminho relativo do arquivo
            
        Returns:
            Conjunto de símbolos declarados
        """
        pass
    
    @abstractmethod
    def extract_imports(self, content: str) -> Set[str]:
        """
        Extrai imports/includes do conteúdo do arquivo.
        
        Args:
            content: Conteúdo do arquivo
            
        Returns:
            Conjunto de arquivos/módulos importados
        """
        pass
    
    @abstractmethod
    def extract_symbol_usage(self, content: str) -> Set[Tuple[str, str]]:
        """
        Extrai uso de símbolos do conteúdo do arquivo.
        
        Args:
            content: Conteúdo do arquivo
            
        Returns:
            Conjunto de tuplas (símbolo, tipo_de_uso)
        """
        pass
    
    def remove_comments(self, content: str) -> str:
        """
        Remove comentários do código para evitar falsos positivos.
        
        Args:
            content: Conteúdo original
            
        Returns:
            Conteúdo sem comentários
        """
        # Remove comentários de linha //
        lines = content.split('\n')
        cleaned_lines = []
        
        in_multiline_comment = False
        for line in lines:
            # Tratar comentários multilinha /* */
            if '/*' in line and '*/' in line:
                # Comentário inline
                parts = line.split('/*')
                result = parts[0]
                for part in parts[1:]:
                    if '*/' in part:
                        after_comment = part.split('*/', 1)[1]
                        result += after_comment
                cleaned_lines.append(result)
            elif '/*' in line:
                # Início de comentário multilinha
                cleaned_lines.append(line.split('/*')[0])
                in_multiline_comment = True
            elif '*/' in line and in_multiline_comment:
                # Fim de comentário multilinha
                cleaned_lines.append(line.split('*/', 1)[1] if '*/' in line else '')
                in_multiline_comment = False
            elif in_multiline_comment:
                # Dentro de comentário multilinha
                cleaned_lines.append('')
            elif '//' in line:
                # Comentário de linha
                cleaned_lines.append(line.split('//')[0])
            else:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    @staticmethod
    def is_valid_symbol(symbol: str, common_keywords: Set[str]) -> bool:
        """
        Verifica se um símbolo é válido e não é uma palavra-chave comum.
        
        Args:
            symbol: Símbolo a verificar
            common_keywords: Conjunto de palavras-chave comuns a ignorar
            
        Returns:
            True se o símbolo for válido
        """
        if not symbol:
            return False
        
        if symbol in common_keywords:
            return False
        
        # Ignorar símbolos muito curtos (provavelmente genéricos)
        if len(symbol) <= 2:
            return False
        
        # Ignorar símbolos que começam com números
        if symbol[0].isdigit():
            return False
        
        return True