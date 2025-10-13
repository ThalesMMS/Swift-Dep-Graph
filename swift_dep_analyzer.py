#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Swift Dependency Analyzer - Ferramenta modular para análise de dependências em projetos iOS.

Analisa dependências entre arquivos Objective-C/C++ e Swift, gerando grafos de
dependência com informações detalhadas sobre uso de símbolos e imports.

Como usar:
    # Analisar um projeto
    python swift_dep_analyzer.py /path/to/project
    
    # Analisar um arquivo específico
    python swift_dep_analyzer.py /path/to/file.swift
    
    # Detectar ciclos
    python swift_dep_analyzer.py /path/to/project --detect-cycles
    
    # Encontrar arquivos órfãos
    python swift_dep_analyzer.py /path/to/project --find-orphans
    
    # Gerar projeto de teste
    python swift_dep_analyzer.py --test
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, List

# Importar módulos do pacote
from swift_dependency_analyzer.constants import SUPPORTED_EXTS
from swift_dependency_analyzer.utils import (
    find_xcode_project_root, 
    normalize_rel,
    should_ignore_path,
    CacheManager,
    ConfigManager
)
from swift_dependency_analyzer.graph import GraphBuilder, GraphAnalyzer
from swift_dependency_analyzer.output import OutputExporter
from swift_dependency_analyzer.test_generator import TestProjectGenerator


class SwiftDependencyAnalyzer:
    """
    Classe principal para análise de dependências.
    """
    
    def __init__(self, args):
        """
        Inicializa o analisador com argumentos da linha de comando.
        
        Args:
            args: Argumentos parseados do argparse
        """
        self.args = args
        self.config = ConfigManager(args.config)
        self.cache_manager = CacheManager()
        
        # Aplicar configurações dos argumentos sobre as do arquivo
        if args.ignore:
            self.config.set('ignore_patterns', 
                          self.config.get_ignore_patterns() + args.ignore)
        
        if args.extended:
            self.config.set('shallow_mode', False)
        
        if args.include_modules:
            self.config.set('include_modules', True)
        
        if args.no_cache:
            self.config.set('cache_enabled', False)
    
    def run(self):
        """
        Executa a análise principal.
        """
        # Comandos especiais
        if self.args.clear:
            self._clear_output()
            return
        
        if self.args.test:
            self._generate_test_project()
            return
        
        # Análise principal
        self._analyze_project()
    
    def _clear_output(self):
        """
        Limpa a pasta output.
        """
        import shutil
        output_dir = Path.cwd() / 'output'
        if output_dir.exists():
            shutil.rmtree(output_dir)
            print('🧹 Pasta output removida com sucesso')
        else:
            print('ℹ️  Pasta output não existe')
    
    def _generate_test_project(self):
        """
        Gera projeto de teste.
        """
        generator = TestProjectGenerator()
        generator.generate()
    
    def _analyze_project(self):
        """
        Realiza a análise do projeto ou arquivo.
        """
        # Determinar caminho de entrada
        input_path = Path(self.args.path).resolve()
        
        # Se é o path padrão e não existe, criar projeto de teste
        if self.args.path == 'test_project' and not input_path.exists():
            print('📦 Projeto test_project não encontrado. Criando automaticamente...\n')
            generator = TestProjectGenerator()
            generator.generate()
            print('\n' + '='*60 + '\n')
            input_path = Path('test_project').resolve()
        
        # Verificar se o path existe
        if not input_path.exists():
            print(f'Erro: caminho não encontrado: {input_path}')
            print(f'\nDica: Use --test para criar um projeto de teste')
            sys.exit(1)
        
        # Determinar raiz e arquivo alvo
        if input_path.is_file():
            root = find_xcode_project_root(input_path)
            target_file = normalize_rel(root, input_path)
            print(f'Arquivo detectado: {input_path.name}')
            print(f'Raiz do projeto detectada: {root}')
        else:
            root = input_path
            target_file = None
            print(f'Usando diretório como raiz do projeto: {root}')
        
        # Construir grafo
        print('\nAnalisando projeto...')
        graph = self._build_graph(root)
        
        # Determinar diretório de saída
        output_dir = self._get_output_dir(input_path, root)
        
        # Exportar resultados
        exporter = OutputExporter(output_dir)
        self._export_results(graph, exporter, root, target_file)
        
        # Análises adicionais
        analyzer = GraphAnalyzer(graph)
        
        if self.args.detect_cycles:
            self._detect_cycles(analyzer, exporter)
        
        if self.args.find_orphans:
            self._find_orphans(analyzer, exporter, root)
        
        # Análise de arquivo específico
        if target_file:
            self._analyze_file(target_file, graph, analyzer, exporter, root)
    
    def _build_graph(self, root: Path) -> dict:
        """
        Constrói o grafo de dependências.
        
        Args:
            root: Raiz do projeto
            
        Returns:
            Grafo de adjacência
        """
        # Verificar cache
        cache_key = None
        if self.config.is_cache_enabled():
            cache_key = self.cache_manager.get_cache_key(root, SUPPORTED_EXTS)
            cached = self.cache_manager.load(cache_key)
            if cached and 'graph' in cached:
                print('  Usando cache de análise anterior')
                return cached['graph']
        
        # Construir grafo
        shallow = self.config.get('shallow_mode', True)
        if shallow:
            print('  Modo shallow (padrão): analisando apenas símbolos diretamente usados')
        else:
            print('  Modo extended: incluindo todos imports e símbolos')
        
        builder = GraphBuilder(root, self.config.get_ignore_patterns())
        graph = builder.build(shallow)
        
        # Salvar no cache
        if cache_key:
            self.cache_manager.save(cache_key, {'graph': graph})
        
        return graph
    
    def _get_output_dir(self, input_path: Path, root: Path) -> Path:
        """
        Determina o diretório de saída.
        
        Args:
            input_path: Caminho de entrada
            root: Raiz do projeto
            
        Returns:
            Diretório de saída
        """
        if self.args.output_dir:
            return Path(self.args.output_dir).resolve()
        
        base_output_dir = Path.cwd() / 'output'
        if input_path.is_file():
            return base_output_dir / input_path.stem
        else:
            return base_output_dir / root.name
    
    def _export_results(self, graph: dict, exporter: OutputExporter, 
                       root: Path, target_file: Optional[str]):
        """
        Exporta os resultados básicos.
        
        Args:
            graph: Grafo de dependências
            exporter: Exportador de saída
            root: Raiz do projeto
            target_file: Arquivo alvo (se houver)
        """
        # Determinar formatos de saída
        formats = ['json', 'dot']
        if self.args.mermaid:
            formats.append('mermaid')
        if self.args.csv:
            formats.append('csv')
        
        # Exportar grafo
        paths = exporter.export_graph(graph, formats)
        
        print(f'\nGrafo salvo em:')
        for format_name, path in paths.items():
            print(f'  - {path}')
        
        # Exportar métricas se CSV foi solicitado
        if self.args.csv:
            analyzer = GraphAnalyzer(graph)
            metrics = analyzer.calculate_metrics()
            metrics_path = exporter.export_metrics(metrics)
            print(f'  - {metrics_path}')
    
    def _detect_cycles(self, analyzer: GraphAnalyzer, exporter: OutputExporter):
        """
        Detecta e reporta ciclos.
        
        Args:
            analyzer: Analisador de grafo
            exporter: Exportador de saída
        """
        print('\n🔍 Detectando dependências circulares...')
        cycles = analyzer.find_cycles()
        
        if cycles:
            print(f'\n⚠️  Encontrados {len(cycles)} ciclos:')
            for i, cycle in enumerate(cycles, 1):
                print(f'\nCiclo {i}:')
                for j, node in enumerate(cycle):
                    if j == len(cycle) - 1:
                        print(f'  └─> {node} (volta ao início)')
                    else:
                        print(f'  ├─> {node}')
            
            path = exporter.export_cycles(cycles)
            print(f'\nCiclos salvos em: {path}')
        else:
            print('✅ Nenhuma dependência circular detectada!')
    
    def _find_orphans(self, analyzer: GraphAnalyzer, exporter: OutputExporter, 
                     root: Path):
        """
        Encontra e reporta arquivos órfãos.
        
        Args:
            analyzer: Analisador de grafo
            exporter: Exportador de saída
            root: Raiz do projeto
        """
        print('\n🔍 Procurando arquivos órfãos...')
        orphans = analyzer.find_orphan_files(root, self.config.get_ignore_patterns())
        
        if orphans:
            print(f'\n📦 Encontrados {len(orphans)} arquivos órfãos:')
            for orphan in orphans[:20]:
                print(f'  - {orphan}')
            if len(orphans) > 20:
                print(f'  ... e mais {len(orphans) - 20} arquivos')
            
            path = exporter.export_orphans(orphans)
            print(f'\nLista completa salva em: {path}')
        else:
            print('✅ Nenhum arquivo órfão encontrado!')
    
    def _analyze_file(self, target_file: str, graph: dict, 
                     analyzer: GraphAnalyzer, exporter: OutputExporter, 
                     root: Path):
        """
        Analisa um arquivo específico.
        
        Args:
            target_file: Arquivo alvo
            graph: Grafo de dependências
            analyzer: Analisador de grafo
            exporter: Exportador de saída
            root: Raiz do projeto
        """
        # Se --showPath foi especificado, mostrar caminhos
        if self.args.showPath:
            self._show_paths(target_file, graph, analyzer, exporter, root)
            return
        
        # Caso contrário, calcular fecho transitivo (se não desabilitado)
        if not self.args.no_closure:
            self._calculate_closure(target_file, analyzer, exporter)
    
    def _show_paths(self, source: str, graph: dict, analyzer: GraphAnalyzer,
                   exporter: OutputExporter, root: Path):
        """
        Mostra caminhos entre dois arquivos.
        
        Args:
            source: Arquivo de origem
            graph: Grafo de dependências
            analyzer: Analisador de grafo
            exporter: Exportador de saída
            root: Raiz do projeto
        """
        # Normalizar caminho de destino
        target_path = Path(self.args.showPath)
        if target_path.is_absolute():
            try:
                target = str(target_path.relative_to(root))
            except ValueError:
                target = self.args.showPath
        else:
            target = self.args.showPath
        
        # Verificar se ambos existem no grafo
        all_nodes = set(graph.keys())
        for adj in graph.values():
            all_nodes.update(adj.keys())
        
        if source not in all_nodes:
            print(f"\nErro: arquivo de origem '{source}' não encontrado no grafo")
            return
        
        if target not in all_nodes:
            print(f"\nErro: arquivo de destino '{target}' não encontrado no grafo")
            return
        
        print(f'\nProcurando caminhos de {source} para {target}...')
        
        # Encontrar caminhos
        paths = analyzer.find_all_paths(source, target)
        
        if not paths:
            print(f'\nNenhum caminho encontrado de {source} para {target}')
        else:
            print(f'\nEncontrados {len(paths)} caminho(s):')
            
            for i, path in enumerate(paths, 1):
                print(f'\nCaminho {i} (comprimento: {len(path)}):')
                formatted = analyzer.format_path_with_labels(path)
                print(formatted)
            
            # Exportar para arquivo
            path_file = exporter.export_paths(paths, source, target, graph)
            print(f'\nCaminhos salvos em: {path_file}')
    
    def _calculate_closure(self, target_file: str, analyzer: GraphAnalyzer,
                          exporter: OutputExporter):
        """
        Calcula e exporta o fecho transitivo.
        
        Args:
            target_file: Arquivo alvo
            analyzer: Analisador de grafo
            exporter: Exportador de saída
        """
        include_modules = self.config.get('include_modules', False)
        
        if self.args.direct_deps_only:
            # Apenas dependências diretas
            closure = list(analyzer.graph.get(target_file, {}).keys())
            print(f'\nDependências diretas de {target_file}:')
        else:
            # Fecho transitivo completo
            closure = analyzer.transitive_closure(target_file, include_modules)
            print(f'\nFecho transitivo de {target_file} ({"com" if include_modules else "sem"} módulos):')
        
        # Filtrar arquivos ignorados
        ignore_patterns = self.config.get_ignore_patterns()
        display_closure = [
            n for n in closure 
            if not should_ignore_path(n, ignore_patterns)
        ]
        
        if ignore_patterns:
            print(f'(Ignorando: {", ".join(ignore_patterns)})')
        
        shallow = self.config.get('shallow_mode', True)
        if shallow:
            print('(Modo shallow: apenas símbolos diretamente usados)')
        else:
            print('(Modo extended: incluindo todos imports e símbolos)')
        
        # Mostrar resultados
        for n in display_closure:
            if self.args.direct_deps_only and target_file in analyzer.graph:
                labels = analyzer.graph[target_file].get(n, [])
                if labels:
                    print(f'  - {n} [{", ".join(labels)}]')
                else:
                    print(f'  - {n}')
            else:
                print(f'  - {n}')
        
        # Exportar para arquivo
        path = exporter.export_closure(
            display_closure, target_file, include_modules, ignore_patterns
        )
        print(f'\nFecho transitivo salvo em: {path}')


def main():
    """
    Função principal.
    """
    parser = argparse.ArgumentParser(
        description="Swift Dependency Analyzer - Análise modular de dependências iOS"
    )
    
    # Argumentos principais
    parser.add_argument('path', nargs='?', default='test_project',
                       help='Arquivo ou diretório do projeto (padrão: test_project)')
    
    # Opções de análise
    parser.add_argument('--extended', action='store_true',
                       help='Análise estendida: inclui todos imports e símbolos')
    parser.add_argument('--no-closure', action='store_true',
                       help='Desabilitar cálculo de fecho transitivo para arquivos')
    parser.add_argument('--include-modules', action='store_true',
                       help='Incluir módulos externos no fecho transitivo')
    parser.add_argument('--direct-deps-only', action='store_true',
                       help='Mostrar apenas dependências diretas')
    parser.add_argument('--showPath', default=None,
                       help='Mostrar caminhos para arquivo de destino')
    
    # Análises especiais
    parser.add_argument('--detect-cycles', action='store_true',
                       help='Detectar dependências circulares')
    parser.add_argument('--find-orphans', action='store_true',
                       help='Encontrar arquivos órfãos')
    
    # Opções de saída
    parser.add_argument('--output-dir', default=None,
                       help='Diretório para salvar os arquivos de saída')
    parser.add_argument('--mermaid', action='store_true',
                       help='Gerar diagrama no formato Mermaid')
    parser.add_argument('--csv', action='store_true',
                       help='Exportar grafo e métricas para CSV')
    
    # Configuração
    parser.add_argument('--config', default=None,
                       help='Arquivo de configuração (.swiftdeprc)')
    parser.add_argument('--ignore', action='append',
                       help='Paths a ignorar (ex: --ignore Pods)')
    parser.add_argument('--no-cache', action='store_true',
                       help='Desabilitar uso de cache')
    
    # Comandos especiais
    parser.add_argument('--test', action='store_true',
                       help='Criar projeto de teste')
    parser.add_argument('--clear', action='store_true',
                       help='Limpar pasta output')
    
    args = parser.parse_args()
    
    # Executar análise
    analyzer = SwiftDependencyAnalyzer(args)
    analyzer.run()


if __name__ == '__main__':
    main()