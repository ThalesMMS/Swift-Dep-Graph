"""
Utilitários para manipulação de arquivos.
"""

from pathlib import Path
from typing import Set, Optional, List, Iterator


def read_text(path: Path) -> str:
    """
    Lê o conteúdo de um arquivo de forma segura.
    
    Args:
        path: Caminho do arquivo
        
    Returns:
        Conteúdo do arquivo ou string vazia em caso de erro
    """
    try:
        return path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return ''


def normalize_rel(root: Path, path: Path) -> str:
    """
    Normaliza um caminho para relativo à raiz.
    
    Args:
        root: Diretório raiz
        path: Caminho a normalizar
        
    Returns:
        Caminho relativo como string
    """
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


def find_xcode_project_root(path: Path) -> Path:
    """
    Encontra a raiz do projeto Xcode a partir de um arquivo ou diretório.
    
    Args:
        path: Caminho inicial
        
    Returns:
        Raiz do projeto
    """
    current = path if path.is_dir() else path.parent
    
    # Subir na hierarquia procurando por indicadores de projeto
    while current != current.parent:
        # Verificar indicadores de projeto Xcode
        if any(current.glob('*.xcodeproj')):
            return current
        if any(current.glob('*.xcworkspace')):
            return current
        if (current / 'Package.swift').exists():
            return current
        if (current / '.git').exists():
            return current
        current = current.parent
    
    # Se não encontrou nada, retorna o diretório do arquivo ou o próprio diretório
    return path if path.is_dir() else path.parent


def should_ignore_path(rel_path: str, ignore_paths: List[str]) -> bool:
    """
    Verifica se um caminho deve ser ignorado.
    
    Args:
        rel_path: Caminho relativo do arquivo
        ignore_paths: Lista de paths/padrões a ignorar
        
    Returns:
        True se o caminho deve ser ignorado
    """
    if not ignore_paths:
        return False
    
    for ignore_pattern in ignore_paths:
        # Normalizar o padrão para garantir que funcione como prefixo de diretório
        if not ignore_pattern.endswith('/'):
            pattern_with_slash = ignore_pattern + '/'
        else:
            pattern_with_slash = ignore_pattern
        
        # Verificar se o caminho relativo começa com o padrão
        if rel_path.startswith(pattern_with_slash) or rel_path.startswith(ignore_pattern + '/'):
            return True
        # Também verificar match exato (para arquivos específicos)
        if rel_path == ignore_pattern:
            return True
    
    return False


def iter_source_files(root: Path, allowed_exts: Set[str], 
                     ignore_paths: Optional[List[str]] = None) -> Iterator[Path]:
    """
    Itera sobre arquivos fonte no projeto.
    
    Args:
        root: Diretório raiz do projeto
        allowed_exts: Conjunto de extensões permitidas
        ignore_paths: Lista de paths a ignorar
        
    Yields:
        Caminhos dos arquivos fonte
    """
    ignore_paths = ignore_paths or []
    
    for p in root.rglob('*'):
        if p.is_file() and p.suffix in allowed_exts:
            # Verificar se o arquivo está em um path ignorado
            rel_path = normalize_rel(root, p)
            
            if not should_ignore_path(rel_path, ignore_paths):
                yield p