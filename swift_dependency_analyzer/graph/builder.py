"""
Construtor de grafos de dependência.
"""

from pathlib import Path
from collections import defaultdict
from typing import Dict, Set, Tuple, Optional, List
from ..parsers import ObjCParser, SwiftParser
from ..constants import OBJC_EXTS, SWIFT_EXTS, SUPPORTED_EXTS
from ..utils.file_utils import read_text, normalize_rel, iter_source_files


class GraphBuilder:
    """
    Constrói grafos de dependência a partir de código fonte.
    """
    
    def __init__(self, root: Path, ignore_paths: Optional[List[str]] = None):
        """
        Inicializa o construtor de grafos.
        
        Args:
            root: Diretório raiz do projeto
            ignore_paths: Lista de caminhos a ignorar
        """
        self.root = root
        self.ignore_paths = ignore_paths or []
        self.objc_parser = ObjCParser()
        self.swift_parser = SwiftParser()
        
        # Índices para mapeamento de símbolos
        self.symbols_declared = defaultdict(set)
        self.symbol_to_file = {}
        self.file_extensions = {}
        
        # Dados de bridging header
        self.bridging_header = None
        self.bridging_header_imports = set()
        self.bridging_header_files = set()
    
    def build(self, shallow: bool = True) -> Dict[str, Dict[str, List[str]]]:
        """
        Constrói o grafo de dependências.
        
        Args:
            shallow: Se True, apenas dependências baseadas em símbolos usados
            
        Returns:
            Grafo de adjacência com labels
        """
        # Detectar bridging header
        self._detect_bridging_header()
        
        # Coletar declarações
        self._collect_declarations()
        
        # Coletar imports e usos
        imports, uses = self._collect_imports_and_usages()
        
        # Construir grafo
        return self._build_graph(imports, uses, shallow)
    
    def _detect_bridging_header(self):
        """
        Detecta e processa o bridging header do projeto.
        """
        patterns = [
            '*-Bridging-Header.h',
            '*/*-Bridging-Header.h',
            '*Bridging-Header.h',
            '*/BridgingHeader.h'
        ]
        
        for pattern in patterns:
            matches = list(self.root.glob(pattern))
            if matches:
                self.bridging_header = matches[0]
                break
        
        if self.bridging_header:
            self._process_bridging_header()
    
    def _process_bridging_header(self):
        """
        Processa o conteúdo do bridging header.
        """
        content = read_text(self.bridging_header)
        
        # Coletar todos os arquivos disponíveis por basename
        all_files_by_basename = {}
        for f in iter_source_files(self.root, SUPPORTED_EXTS, self.ignore_paths):
            rel = normalize_rel(self.root, f)
            all_files_by_basename.setdefault(f.name, set()).add(rel)
        
        # Extrair imports usando o parser ObjC
        imports = self.objc_parser.extract_imports(content)
        
        for imp in imports:
            if not imp.startswith('@module:'):
                basename = Path(imp).name
                self.bridging_header_imports.add(basename)
                # Resolver para arquivos completos
                for candidate in all_files_by_basename.get(basename, []):
                    self.bridging_header_files.add(candidate)
    
    def _collect_declarations(self):
        """
        Coleta todas as declarações de símbolos no projeto.
        """
        for f in iter_source_files(self.root, SUPPORTED_EXTS, self.ignore_paths):
            content = read_text(f)
            rel = normalize_rel(self.root, f)
            self.file_extensions[rel] = f.suffix
            
            # Escolher parser baseado na extensão
            if f.suffix in OBJC_EXTS:
                parser = self.objc_parser
            elif f.suffix in SWIFT_EXTS:
                parser = self.swift_parser
            else:
                continue
            
            # Extrair declarações
            declarations = parser.extract_declarations(content, rel)
            
            for symbol in declarations:
                self.symbols_declared[rel].add(symbol)
                # Extensions não sobrescrevem o arquivo original
                if not symbol.startswith('extension:'):
                    self.symbol_to_file.setdefault(symbol, rel)
    
    def _collect_imports_and_usages(self) -> Tuple[Dict, Dict]:
        """
        Coleta imports e uso de símbolos.
        
        Returns:
            Tupla (imports, uses)
        """
        imports = defaultdict(set)
        uses = defaultdict(set)
        
        # Criar índice de arquivos por basename
        all_files_by_basename = {}
        for f in iter_source_files(self.root, SUPPORTED_EXTS, self.ignore_paths):
            rel = normalize_rel(self.root, f)
            all_files_by_basename.setdefault(f.name, set()).add(rel)
        
        for f in iter_source_files(self.root, SUPPORTED_EXTS, self.ignore_paths):
            content = read_text(f)
            rel = normalize_rel(self.root, f)
            
            # Escolher parser
            if f.suffix in OBJC_EXTS:
                parser = self.objc_parser
            elif f.suffix in SWIFT_EXTS:
                parser = self.swift_parser
            else:
                continue
            
            # Extrair imports
            file_imports = parser.extract_imports(content)
            for imp in file_imports:
                if imp.startswith('@module:') or imp.startswith('module:'):
                    imports[rel].add(imp)
                else:
                    # Resolver arquivo local por basename
                    basename = Path(imp).name
                    for candidate in all_files_by_basename.get(basename, []):
                        imports[rel].add(candidate)
            
            # Extrair uso de símbolos
            symbol_uses = parser.extract_symbol_usage(content)
            uses[rel].update(symbol_uses)
        
        return imports, uses
    
    def _build_graph(self, imports: Dict, uses: Dict, shallow: bool) -> Dict[str, Dict[str, List[str]]]:
        """
        Constrói o grafo final com labels.
        
        Args:
            imports: Mapeamento de imports
            uses: Mapeamento de uso de símbolos
            shallow: Modo shallow (apenas símbolos usados)
            
        Returns:
            Grafo de adjacência com labels
        """
        adj = defaultdict(lambda: defaultdict(set))
        
        if shallow:
            # Modo shallow: apenas dependências baseadas em símbolos usados
            self._add_symbol_dependencies(adj, uses)
            
            # Adicionar dependências via bridging header para arquivos Swift
            if self.bridging_header_files:
                self._add_bridging_dependencies(adj, uses)
            
            # Adicionar módulos apenas se houver uso direto
            self._add_module_dependencies_shallow(adj, imports, uses)
        else:
            # Modo extended: incluir todos imports e usos
            self._add_import_dependencies(adj, imports)
            self._add_symbol_dependencies(adj, uses)
        
        # Normalizar para formato final
        graph = {}
        for source, targets in adj.items():
            graph[source] = {
                target: sorted(list(labels)) 
                for target, labels in targets.items()
            }
        
        return graph
    
    def _add_symbol_dependencies(self, adj: Dict, uses: Dict):
        """
        Adiciona dependências baseadas em uso de símbolos.
        """
        for source_file, usages in uses.items():
            for symbol, kind in usages:
                target_file = self._resolve_symbol_to_file(symbol)
                
                if target_file and target_file != source_file:
                    if self._is_valid_dependency(source_file, target_file):
                        label = f'{symbol}[{kind}]' if kind else symbol
                        adj[source_file][target_file].add(label)
    
    def _add_bridging_dependencies(self, adj: Dict, uses: Dict):
        """
        Adiciona dependências de arquivos Swift para ObjC via bridging header.
        """
        for source_file in uses.keys():
            # Verificar se é um arquivo Swift
            if self.file_extensions.get(source_file, '') == '.swift':
                # Para cada símbolo usado pelo arquivo Swift
                for symbol, kind in uses[source_file]:
                    base_symbol = symbol.split('.', 1)[0] if '.' in symbol else symbol
                    
                    # Verificar se o símbolo está declarado em arquivo do bridging header
                    for bridging_file in self.bridging_header_files:
                        if base_symbol in self.symbols_declared.get(bridging_file, set()):
                            label = f'{symbol}[{kind}]'
                            adj[source_file][bridging_file].add(label)
    
    def _add_module_dependencies_shallow(self, adj: Dict, imports: Dict, uses: Dict):
        """
        Adiciona dependências de módulos no modo shallow.
        """
        for source_file, imported in imports.items():
            for item in imported:
                if item.startswith('@module:') or item.startswith('module:'):
                    # Verificar se há uso de símbolos que poderiam vir do módulo
                    if any(symbol for symbol, _ in uses.get(source_file, []) if '.' not in symbol):
                        adj[source_file][item].add('<module-import>')
    
    def _add_import_dependencies(self, adj: Dict, imports: Dict):
        """
        Adiciona dependências baseadas em imports diretos.
        """
        for source_file, imported in imports.items():
            for item in imported:
                if item.startswith('@module:') or item.startswith('module:'):
                    adj[source_file][item].add('<module-import>')
                else:
                    adj[source_file][item].add('<import>')
    
    def _resolve_symbol_to_file(self, symbol: str) -> Optional[str]:
        """
        Resolve um símbolo para o arquivo que o declara.
        
        Args:
            symbol: Nome do símbolo
            
        Returns:
            Caminho do arquivo ou None
        """
        # Se o símbolo tem formato Classe.método, tentar resolver pela classe
        if '.' in symbol:
            base = symbol.split('.', 1)[0]
            return self.symbol_to_file.get(base)
        else:
            return self.symbol_to_file.get(symbol)
    
    def _is_valid_dependency(self, source: str, target: str) -> bool:
        """
        Verifica se uma dependência é válida entre dois arquivos.
        
        Args:
            source: Arquivo de origem
            target: Arquivo de destino
            
        Returns:
            True se a dependência for válida
        """
        # Módulos sempre são válidos
        if source.startswith(('module:', '@module:')) or target.startswith(('module:', '@module:')):
            return True
        
        source_ext = self.file_extensions.get(source, '')
        target_ext = self.file_extensions.get(target, '')
        
        # Swift pode importar Swift
        if source_ext == '.swift' and target_ext == '.swift':
            return True
        
        # ObjC pode importar ObjC
        if source_ext in OBJC_EXTS and target_ext in OBJC_EXTS:
            return True
        
        # Swift pode importar ObjC via bridging header
        if source_ext == '.swift' and target_ext in OBJC_EXTS:
            target_name = Path(target).name
            return target_name in self.bridging_header_imports or self.bridging_header is not None
        
        # ObjC não pode importar Swift diretamente
        if source_ext in OBJC_EXTS and target_ext == '.swift':
            return False
        
        return True