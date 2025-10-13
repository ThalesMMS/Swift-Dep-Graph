"""
Gerenciador de cache para otimização de análises.
"""

import pickle
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from .file_utils import iter_source_files


class CacheManager:
    """
    Gerencia cache de análises para evitar reprocessamento.
    """
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Inicializa o gerenciador de cache.
        
        Args:
            cache_dir: Diretório para armazenar cache
        """
        self.cache_dir = cache_dir or (Path.home() / '.swift-dep-cache')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_cache_key(self, root: Path, supported_exts: set) -> str:
        """
        Gera uma chave de cache única para o projeto.
        
        Args:
            root: Raiz do projeto
            supported_exts: Extensões suportadas
            
        Returns:
            Chave de cache como string hex
        """
        hasher = hashlib.md5()
        hasher.update(str(root).encode())
        
        # Incluir timestamps dos arquivos mais recentes
        files = list(iter_source_files(root, supported_exts, ignore_paths=None))
        if files:
            # Amostra dos primeiros 100 arquivos para performance
            sample_files = files[:100]
            latest_mtime = max(f.stat().st_mtime for f in sample_files)
            hasher.update(str(latest_mtime).encode())
        
        return hasher.hexdigest()
    
    def load(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Carrega dados do cache.
        
        Args:
            cache_key: Chave do cache
            
        Returns:
            Dados do cache ou None se não existir/inválido
        """
        cache_file = self.cache_dir / f'{cache_key}.pkl'
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        except Exception:
            # Cache corrompido ou incompatível
            return None
    
    def save(self, cache_key: str, data: Dict[str, Any]) -> bool:
        """
        Salva dados no cache.
        
        Args:
            cache_key: Chave do cache
            data: Dados a salvar
            
        Returns:
            True se salvou com sucesso
        """
        cache_file = self.cache_dir / f'{cache_key}.pkl'
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(data, f)
            return True
        except Exception:
            return False
    
    def clear(self) -> int:
        """
        Limpa todo o cache.
        
        Returns:
            Número de arquivos removidos
        """
        count = 0
        for cache_file in self.cache_dir.glob('*.pkl'):
            try:
                cache_file.unlink()
                count += 1
            except Exception:
                pass
        return count
    
    def get_cache_size(self) -> int:
        """
        Obtém o tamanho total do cache em bytes.
        
        Returns:
            Tamanho em bytes
        """
        total = 0
        for cache_file in self.cache_dir.glob('*.pkl'):
            try:
                total += cache_file.stat().st_size
            except Exception:
                pass
        return total