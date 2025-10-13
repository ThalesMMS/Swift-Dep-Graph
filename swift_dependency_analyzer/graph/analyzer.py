"""
Analisador de grafos de dependência.
"""

from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from ..utils.file_utils import normalize_rel, iter_source_files
from ..constants import SUPPORTED_EXTS


class GraphAnalyzer:
    """
    Analisa grafos de dependência para extrair métricas e padrões.
    """
    
    def __init__(self, graph: Dict[str, Dict[str, List[str]]]):
        """
        Inicializa o analisador.
        
        Args:
            graph: Grafo de adjacência com labels
        """
        self.graph = graph
    
    def find_cycles(self) -> List[List[str]]:
        """
        Detecta ciclos no grafo usando DFS.
        
        Returns:
            Lista de ciclos encontrados
        """
        def dfs_cycle(node, visited, rec_stack, path, cycles):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self.graph.get(node, {}):
                if neighbor in rec_stack:
                    # Encontrou um ciclo
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)
                elif neighbor not in visited:
                    dfs_cycle(neighbor, visited, rec_stack, path, cycles)
            
            path.pop()
            rec_stack.remove(node)
            return cycles
        
        visited = set()
        cycles = []
        
        for node in self.graph:
            if node not in visited:
                rec_stack = set()
                path = []
                dfs_cycle(node, visited, rec_stack, path, cycles)
        
        # Remover ciclos duplicados
        unique_cycles = []
        seen = set()
        for cycle in cycles:
            normalized = tuple(sorted(cycle[:-1]))  # Excluir último (duplicado do primeiro)
            if normalized not in seen:
                seen.add(normalized)
                unique_cycles.append(cycle)
        
        return unique_cycles
    
    def find_all_paths(self, start: str, end: str, max_depth: int = 10) -> List[List[str]]:
        """
        Encontra todos os caminhos entre dois vértices usando BFS.
        
        Args:
            start: Vértice de origem
            end: Vértice de destino
            max_depth: Profundidade máxima
            
        Returns:
            Lista de caminhos ordenados por comprimento
        """
        if start == end:
            return [[start]]
        
        all_paths = []
        queue = deque([(start, [start])])
        visited_paths = set()
        
        while queue:
            current, path = queue.popleft()
            
            if len(path) > max_depth:
                continue
            
            for neighbor in self.graph.get(current, {}):
                if neighbor not in path:
                    new_path = path + [neighbor]
                    path_tuple = tuple(new_path)
                    
                    if path_tuple in visited_paths:
                        continue
                    
                    visited_paths.add(path_tuple)
                    
                    if neighbor == end:
                        all_paths.append(new_path)
                    else:
                        queue.append((neighbor, new_path))
        
        return all_paths
    
    def format_path_with_labels(self, path: List[str]) -> str:
        """
        Formata um caminho incluindo os labels das arestas.
        
        Args:
            path: Lista de vértices formando um caminho
            
        Returns:
            String formatada representando o caminho
        """
        if not path:
            return ""
        
        formatted = []
        for i in range(len(path) - 1):
            source = path[i]
            target = path[i + 1]
            
            labels = self.graph.get(source, {}).get(target, [])
            
            # Filtrar labels relevantes
            relevant_labels = [
                label for label in labels 
                if not label.startswith('<') and label not in ['<import>', '<module-import>']
            ]
            
            if relevant_labels:
                formatted.append(f"{source} -> {relevant_labels[0]} -> {target}")
            else:
                formatted.append(f"{source} -> {target}")
        
        return "\n".join(formatted)
    
    def find_orphan_files(self, root: Path, ignore_paths: Optional[List[str]] = None) -> List[str]:
        """
        Encontra arquivos que não são referenciados.
        
        Args:
            root: Diretório raiz do projeto
            ignore_paths: Caminhos a ignorar
            
        Returns:
            Lista de arquivos órfãos
        """
        ignore_paths = ignore_paths or []
        
        # Coletar todos os arquivos do projeto
        all_files = set()
        for f in iter_source_files(root, SUPPORTED_EXTS, ignore_paths):
            rel = normalize_rel(root, f)
            all_files.add(rel)
        
        # Coletar arquivos referenciados
        referenced = set(self.graph.keys())
        for node, edges in self.graph.items():
            referenced.update(edges.keys())
        
        # Filtrar apenas arquivos locais (não módulos)
        referenced = {
            f for f in referenced 
            if not (f.startswith('module:') or f.startswith('@module:'))
        }
        
        # Arquivos órfãos
        orphans = all_files - referenced
        
        return sorted(orphans)
    
    def calculate_metrics(self) -> Dict:
        """
        Calcula métricas de complexidade do grafo.
        
        Returns:
            Dicionário com métricas
        """
        metrics = {}
        
        # Métricas básicas
        metrics['total_files'] = len(self.graph)
        metrics['total_edges'] = sum(len(edges) for edges in self.graph.values())
        
        # Calcular coupling
        afferent_coupling = defaultdict(int)  # Quantos dependem de mim
        efferent_coupling = defaultdict(int)  # De quantos eu dependo
        
        for source, targets in self.graph.items():
            efferent_coupling[source] = len(targets)
            for target in targets:
                if not (target.startswith('module:') or target.startswith('@module:')):
                    afferent_coupling[target] += 1
        
        # Arquivos mais acoplados
        metrics['most_depended_on'] = sorted(
            [(f, count) for f, count in afferent_coupling.items()],
            key=lambda x: x[1], reverse=True
        )[:10]
        
        metrics['most_dependencies'] = sorted(
            [(f, count) for f, count in efferent_coupling.items()],
            key=lambda x: x[1], reverse=True
        )[:10]
        
        # Média de dependências
        if metrics['total_files'] > 0:
            metrics['avg_dependencies'] = metrics['total_edges'] / metrics['total_files']
        else:
            metrics['avg_dependencies'] = 0
        
        return metrics
    
    def transitive_closure(self, start: str, include_modules: bool = False) -> List[str]:
        """
        Calcula o fecho transitivo direto a partir de um nó.
        
        Args:
            start: Nó inicial
            include_modules: Se True, inclui módulos externos
            
        Returns:
            Lista ordenada de nós alcançáveis
        """
        def is_module(n: str) -> bool:
            return n.startswith('module:') or n.startswith('@module:')
        
        visited = set()
        queue = deque([start])
        
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            
            for neighbor in self.graph.get(current, {}):
                if not include_modules and is_module(neighbor):
                    continue
                if neighbor not in visited:
                    queue.append(neighbor)
        
        visited.discard(start)
        return sorted(visited)