"""
Gerenciador de configurações.
"""

import configparser
from pathlib import Path
from typing import Dict, Any, Optional, List


class ConfigManager:
    """
    Gerencia configurações do analisador.
    """
    
    DEFAULT_CONFIG = {
        'ignore_patterns': [],
        'custom_extensions': [],
        'cache_enabled': True,
        'max_depth': None,
        'shallow_mode': True,
        'include_modules': False
    }
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Inicializa o gerenciador de configurações.
        
        Args:
            config_file: Caminho para arquivo de configuração
        """
        self.config = self.DEFAULT_CONFIG.copy()
        self.config_file = self._find_config_file(config_file)
        
        if self.config_file:
            self._load_config()
    
    def _find_config_file(self, config_file: Optional[str]) -> Optional[Path]:
        """
        Encontra o arquivo de configuração.
        
        Args:
            config_file: Caminho fornecido ou None
            
        Returns:
            Path do arquivo de configuração ou None
        """
        if config_file:
            path = Path(config_file)
            if path.exists():
                return path
        
        # Procurar em locais padrão
        search_paths = [
            Path.cwd() / '.swiftdeprc',
            Path.cwd() / '.swift-dep.conf',
            Path.home() / '.swiftdeprc',
            Path.home() / '.swift-dep.conf'
        ]
        
        for path in search_paths:
            if path.exists():
                return path
        
        return None
    
    def _load_config(self):
        """
        Carrega configurações do arquivo.
        """
        if not self.config_file:
            return
        
        try:
            parser = configparser.ConfigParser()
            
            # Ler arquivo como INI
            with open(self.config_file, 'r') as f:
                # Adicionar seção DEFAULT se não existir
                content = f.read()
                if not content.startswith('['):
                    content = '[DEFAULT]\n' + content
                parser.read_string(content)
            
            # Extrair configurações
            section = parser['DEFAULT']
            
            if 'ignore_patterns' in section:
                self.config['ignore_patterns'] = [
                    p.strip() for p in section['ignore_patterns'].split(',')
                ]
            
            if 'custom_extensions' in section:
                self.config['custom_extensions'] = [
                    e.strip() for e in section['custom_extensions'].split(',')
                ]
            
            if 'cache_enabled' in section:
                self.config['cache_enabled'] = section.getboolean('cache_enabled')
            
            if 'max_depth' in section:
                self.config['max_depth'] = section.getint('max_depth')
            
            if 'shallow_mode' in section:
                self.config['shallow_mode'] = section.getboolean('shallow_mode')
            
            if 'include_modules' in section:
                self.config['include_modules'] = section.getboolean('include_modules')
            
        except Exception as e:
            print(f'Aviso: Erro ao carregar configuração de {self.config_file}: {e}')
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtém um valor de configuração.
        
        Args:
            key: Chave da configuração
            default: Valor padrão se não existir
            
        Returns:
            Valor da configuração
        """
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """
        Define um valor de configuração.
        
        Args:
            key: Chave da configuração
            value: Valor a definir
        """
        self.config[key] = value
    
    def get_ignore_patterns(self) -> List[str]:
        """
        Obtém padrões de ignorar.
        
        Returns:
            Lista de padrões
        """
        return self.config.get('ignore_patterns', [])
    
    def get_custom_extensions(self) -> List[str]:
        """
        Obtém extensões customizadas.
        
        Returns:
            Lista de extensões
        """
        return self.config.get('custom_extensions', [])
    
    def is_cache_enabled(self) -> bool:
        """
        Verifica se o cache está habilitado.
        
        Returns:
            True se cache está habilitado
        """
        return self.config.get('cache_enabled', True)
    
    def get_max_depth(self) -> Optional[int]:
        """
        Obtém profundidade máxima para análise.
        
        Returns:
            Profundidade máxima ou None
        """
        return self.config.get('max_depth')
    
    def save(self, file_path: Optional[Path] = None) -> bool:
        """
        Salva configurações em arquivo.
        
        Args:
            file_path: Caminho do arquivo (usa o atual se None)
            
        Returns:
            True se salvou com sucesso
        """
        path = file_path or self.config_file
        if not path:
            path = Path.cwd() / '.swiftdeprc'
        
        try:
            parser = configparser.ConfigParser()
            parser['DEFAULT'] = {}
            
            if self.config['ignore_patterns']:
                parser['DEFAULT']['ignore_patterns'] = ','.join(self.config['ignore_patterns'])
            
            if self.config['custom_extensions']:
                parser['DEFAULT']['custom_extensions'] = ','.join(self.config['custom_extensions'])
            
            parser['DEFAULT']['cache_enabled'] = str(self.config['cache_enabled'])
            parser['DEFAULT']['shallow_mode'] = str(self.config['shallow_mode'])
            parser['DEFAULT']['include_modules'] = str(self.config['include_modules'])
            
            if self.config['max_depth'] is not None:
                parser['DEFAULT']['max_depth'] = str(self.config['max_depth'])
            
            with open(path, 'w') as f:
                parser.write(f)
            
            return True
        except Exception:
            return False