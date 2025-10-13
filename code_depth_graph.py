#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ESTE ARQUIVO NÃO DEVE SER USADO. ESTÁ AQUI SÓ PARA BACKUP.
"""
Gera grafo de dependências entre arquivos Objective-C / Objective-C++ / Swift.
Arestas A -> B significam "A usa algo declarado em B" ou "A importa B".
Rótulo da aresta armazena o conjunto de símbolos/métodos usados (quando inferível).

Dependências: apenas Python stdlib.

Como usar:
    # Com caminho para arquivo dentro do projeto (detecta raiz automaticamente)
    python code_dep_graph.py /path/to/project/Sources/MyFile.swift
    
    # Com diretório raiz do projeto (modo antigo)
    python code_dep_graph.py /caminho/para/projeto --root-exts .m,.mm,.swift,.h,.hh
    
    # Fecho transitivo (direto) de um arquivo:
    python code_dep_graph.py /path/to/file.m --closure

Sugerido: combine com Graphviz:
    dot -Tpdf graph.dot -o graph.pdf
"""

import argparse
import json
import os
import re
import subprocess
import pickle
import hashlib
import csv
from collections import defaultdict, deque
from pathlib import Path

# --- Configuração de extensões suportadas ---
OBJC_EXTS   = {'.m', '.mm', '.h', '.hh'}
SWIFT_EXTS  = {'.swift'}
SUPPORTED   = OBJC_EXTS | SWIFT_EXTS

# --- Regex aproximadas para declarações (símbolos -> arquivo) ---
# Objective-C declarações:
RE_OBJC_INTERFACE  = re.compile(r'@interface\s+([A-Za-z_]\w*)')
RE_OBJC_PROTOCOL   = re.compile(r'@protocol\s+([A-Za-z_]\w*)')
RE_OBJC_IMPL       = re.compile(r'@implementation\s+([A-Za-z_]\w*)')
RE_OBJC_CATEGORY   = re.compile(r'@interface\s+([A-Za-z_]\w*)\s*\(([A-Za-z_]\w*)\)')
RE_OBJC_ENUM       = re.compile(r'typedef\s+NS_ENUM\s*\([^,]+,\s*([A-Za-z_]\w*)\)')
RE_C_FUNCTION      = re.compile(r'^(?:static\s+)?(?:inline\s+)?(?:extern\s+)?[A-Za-z_]\w*\s+\*?\s*([A-Za-z_]\w*)\s*\(', re.MULTILINE)

# Swift declarações:
RE_SWIFT_TYPE      = re.compile(r'\b(class|struct|enum|protocol)\s+([A-Za-z_]\w*)')
RE_SWIFT_EXT       = re.compile(r'\bextension\s+([A-Za-z_]\w*)')
RE_SWIFT_FUNC_TOP  = re.compile(r'^\s*func\s+([A-Za-z_]\w*)\s*\(', re.MULTILINE)

# --- Regex para imports / referências entre arquivos ---
# Objective-C imports e adiantamentos:
RE_IMPORT_LOCAL    = re.compile(r'#\s*import\s*"([^"]+)"')
RE_INCLUDE_LOCAL   = re.compile(r'#\s*include\s*"([^"]+)"')
RE_OBJC_IMPORT_MOD = re.compile(r'@import\s+([A-Za-z_][\w\.]*)\s*;')
RE_OBJC_CLASS_FWD  = re.compile(r'@class\s+([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*;')

# Swift imports:
RE_SWIFT_IMPORT    = re.compile(r'^\s*import\s+([A-Za-z_][\w\.]*)', re.MULTILINE)

# --- Regex para usos de símbolos (muito aproximadas) ---
# ObjC: [Classe metodo], [obj metodo], Classe *var, id<Proto>
RE_OBJC_MSG_SEND_CLASS = re.compile(r'\[\s*([A-Z][A-Za-z_]\w*)\s+([A-Za-z_]\w*)')  # Classes começam com maiúscula
RE_OBJC_MSG_SEND_OBJ   = re.compile(r'\[\s*([a-z_][A-Za-z_]\w*)\s+([A-Za-z_]\w*)')  # Objetos começam com minúscula
RE_OBJC_TYPE_USAGE     = re.compile(r'\b([A-Z][A-Za-z_]\w*)\s*\*')  # Classe *ptr - classes começam com maiúscula
RE_OBJC_PROTOCOL_USE   = re.compile(r'id\s*<\s*([A-Za-z_]\w*)\s*>')
# Remover RE_C_FUNC_CALL genérico - muito propenso a falsos positivos
# Ao invés disso, procurar apenas por funções C globais conhecidas ou com prefixos específicos
RE_C_FUNC_CALL         = re.compile(r'\b(NS[A-Z]\w*|CF[A-Z]\w*|CG[A-Z]\w*|UI[A-Z]\w*|dispatch_\w+|pthread_\w+)\s*\(')

# Swift: Tipo.método(, obj.método(, : Protocolo, uso de Tipo como anotação
RE_SWIFT_STATIC_CALL   = re.compile(r'\b([A-Z][A-Za-z_]\w*)\s*\.\s*([A-Za-z_]\w*)\s*\(')  # Tipos começam com maiúscula
RE_SWIFT_INST_CALL     = re.compile(r'\b([a-z_][A-Za-z_]\w*)\s*\.\s*([A-Za-z_]\w*)\s*\(')  # Instâncias começam com minúscula
RE_SWIFT_TYPE_ANNOT    = re.compile(r':\s*([A-Z][A-Za-z_]\w*)')  # Tipos começam com maiúscula
RE_SWIFT_PROTO_CONF    = re.compile(r':\s*([A-Z][A-Za-z_]\w*)(?:\s*,|\s*{|\s*where|\s*$)')  # Protocolos começam com maiúscula

def find_xcode_project_root(path: Path) -> Path:
    """
    Encontra a raiz do projeto Xcode a partir de um arquivo ou diretório.
    Procura por .xcodeproj, .xcworkspace, Package.swift, ou .git
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
            # Se encontrou .git, é provavelmente a raiz do projeto
            return current
        current = current.parent
    
    # Se não encontrou nada, retorna o diretório do arquivo ou o próprio diretório
    return path if path.is_dir() else path.parent

def find_bridging_header(root: Path) -> Path:
    """
    Procura por bridging headers no projeto.
    Padrões comuns: *-Bridging-Header.h, */Bridging-Header.h
    """
    # Padrões comuns de bridging headers
    patterns = [
        '*-Bridging-Header.h',
        '*/*-Bridging-Header.h',
        '*Bridging-Header.h',
        '*/BridgingHeader.h'
    ]
    
    for pattern in patterns:
        matches = list(root.glob(pattern))
        if matches:
            return matches[0]
    
    return None

def get_cache_key(root: Path) -> str:
    """
    Gera uma chave de cache baseada no projeto e timestamps dos arquivos.
    """
    hasher = hashlib.md5()
    hasher.update(str(root).encode())
    
    # Incluir timestamps dos arquivos mais recentes
    files = list(iter_source_files(root, SUPPORTED, ignore_paths=None))
    if files:
        latest_mtime = max(f.stat().st_mtime for f in files[:100])  # Amostra dos primeiros 100
        hasher.update(str(latest_mtime).encode())
    
    return hasher.hexdigest()

def load_cache(cache_file: Path) -> dict:
    """
    Carrega o cache se existir e for válido.
    """
    if not cache_file.exists():
        return None
    
    try:
        with open(cache_file, 'rb') as f:
            return pickle.load(f)
    except Exception:
        return None

def save_cache(cache_file: Path, data: dict):
    """
    Salva dados no cache.
    """
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(data, f)
    except Exception:
        pass

def parse_xcconfig_files(root: Path) -> dict:
    """
    Parse .xcconfig files para extrair configurações de build.
    Retorna um dicionário com as configurações encontradas.
    """
    config = {}
    xcconfig_files = list(root.glob('**/*.xcconfig'))
    
    for xcconfig_file in xcconfig_files:
        try:
            content = read_text(xcconfig_file)
            for line in content.split('\n'):
                line = line.strip()
                # Ignorar comentários e linhas vazias
                if not line or line.startswith('//'):
                    continue
                # Parse de key = value
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    config[key] = value
        except Exception:
            continue
    
    return config

def iter_source_files(root: Path, allowed_exts, ignore_paths=None):
    """
    Itera sobre arquivos fonte, opcionalmente ignorando paths específicos.
    
    Args:
        root: Diretório raiz do projeto
        allowed_exts: Conjunto de extensões permitidas
        ignore_paths: Lista de paths a ignorar (relativos à raiz)
    """
    ignore_paths = ignore_paths or []
    
    for p in root.rglob('*'):
        if p.is_file() and p.suffix in allowed_exts:
            # Verificar se o arquivo está em um path ignorado
            rel_path = normalize_rel(root, p)
            should_ignore = False
            
            for ignore_pattern in ignore_paths:
                # Normalizar o padrão para garantir que funcione como prefixo de diretório
                # Se não termina com /, adicionar para garantir que seja um diretório
                if not ignore_pattern.endswith('/'):
                    pattern_with_slash = ignore_pattern + '/'
                else:
                    pattern_with_slash = ignore_pattern
                
                # Verificar se o caminho relativo começa com o padrão
                if rel_path.startswith(pattern_with_slash) or rel_path.startswith(ignore_pattern + '/'):
                    should_ignore = True
                    break
                # Também verificar match exato (para arquivos específicos)
                if rel_path == ignore_pattern:
                    should_ignore = True
                    break
            
            if not should_ignore:
                yield p

def should_ignore_path(rel_path: str, ignore_paths: list) -> bool:
    """
    Verifica se um caminho deve ser ignorado baseado nos padrões fornecidos.
    
    Args:
        rel_path: Caminho relativo do arquivo
        ignore_paths: Lista de paths/padrões a ignorar
    
    Returns:
        True se o caminho deve ser ignorado, False caso contrário
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

def read_text(path: Path):
    try:
        return path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return ''

def normalize_rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)

def collect_declarations(root: Path, ignore_paths=None):
    """
    Constrói um índice de declarações:
      - symbols_declared[file] = {símbolos}
      - symbol_to_file[símbolo] = file
    """
    symbols_declared = defaultdict(set)
    symbol_to_file = {}
    for f in iter_source_files(root, SUPPORTED, ignore_paths):
        text = read_text(f)
        rel = normalize_rel(root, f)
        if f.suffix in OBJC_EXTS:
            # Classes, protocolos, implementação, categorias, enums e funções C
            for m in RE_OBJC_INTERFACE.findall(text):
                symbols_declared[rel].add(m)
                symbol_to_file[m] = rel
            for m in RE_OBJC_PROTOCOL.findall(text):
                symbols_declared[rel].add(m)
                symbol_to_file[m] = rel
            for m in RE_OBJC_IMPL.findall(text):
                symbols_declared[rel].add(m)
                symbol_to_file[m] = rel
            for cls, cat in RE_OBJC_CATEGORY.findall(text):
                cat_name = f'{cls}({cat})'
                symbols_declared[rel].add(cat_name)
                symbol_to_file[cat_name] = rel
            for m in RE_OBJC_ENUM.findall(text):
                symbols_declared[rel].add(m)
                symbol_to_file[m] = rel
            for m in RE_C_FUNCTION.findall(text):
                symbols_declared[rel].add(m)
                # Funções C podem colidir; se colidir, mantemos o primeiro mapeamento
                symbol_to_file.setdefault(m, rel)
        else:  # Swift
            for kind, name in RE_SWIFT_TYPE.findall(text):
                symbols_declared[rel].add(name)
                symbol_to_file[name] = rel
            for name in RE_SWIFT_EXT.findall(text):
                # Extensão não declara novo tipo, mas sinaliza uso do tipo
                symbols_declared[rel].add(f'extension:{name}')
            for fn in RE_SWIFT_FUNC_TOP.findall(text):
                symbols_declared[rel].add(fn)
                symbol_to_file.setdefault(fn, rel)
    return symbols_declared, symbol_to_file

def collect_imports_and_usages(root: Path, symbol_to_file: dict, ignore_paths=None):
    """
    Retorna:
      imports[file] = set(str)     # nomes de arquivos (quando conseguir resolver) ou módulos
      uses[file]    = set((symbol, kind))  kind ∈ {'call','type','proto','func'}
    """
    imports = defaultdict(set)
    uses    = defaultdict(set)
    
    # Conjunto de palavras comuns que devem ser ignoradas para evitar falsos positivos
    COMMON_KEYWORDS = {
        'self', 'super', 'nil', 'null', 'true', 'false', 'YES', 'NO',
        'init', 'dealloc', 'alloc', 'new', 'copy', 'retain', 'release', 'autorelease',
        'description', 'debugDescription', 'hash', 'isEqual', 'class', 'cancel',
        'start', 'stop', 'pause', 'resume', 'reset', 'clear', 'refresh',
        'load', 'save', 'open', 'close', 'read', 'write', 'delete', 'remove',
        'add', 'insert', 'update', 'replace', 'get', 'set', 'count', 'size',
        'begin', 'end', 'first', 'last', 'next', 'previous', 'current',
        'show', 'hide', 'enable', 'disable', 'validate', 'invalidate',
        'connect', 'disconnect', 'send', 'receive', 'process', 'handle',
        'error', 'warning', 'info', 'debug', 'log', 'print', 'format',
        'encode', 'decode', 'serialize', 'deserialize', 'parse', 'stringify',
        # Additional common method names that shouldn't create dependencies
        'startListening', 'stopListening', 'isListening'
    }

    all_files_by_basename = {}
    for p in iter_source_files(root, SUPPORTED, ignore_paths):
        rel = normalize_rel(root, p)
        all_files_by_basename.setdefault(p.name, set()).add(rel)

    for f in iter_source_files(root, SUPPORTED, ignore_paths):
        text = read_text(f)
        rel = normalize_rel(root, f)
        
        # Remover comentários para evitar falsos positivos
        # Remover comentários de linha //
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            # Se tem comentário //, pegar só a parte antes dele
            if '//' in line:
                cleaned_lines.append(line.split('//')[0])
            else:
                cleaned_lines.append(line)
        text_no_comments = '\n'.join(cleaned_lines)
        
        # Para análise de uso de símbolos, usar o texto sem comentários
        analysis_text = text_no_comments

        if f.suffix in OBJC_EXTS:
            # Imports locais (#import/#include "Foo.h")
            for inc in RE_IMPORT_LOCAL.findall(text) + RE_INCLUDE_LOCAL.findall(text):
                # Resolver por basename
                for candidate in all_files_by_basename.get(Path(inc).name, []):
                    imports[rel].add(candidate)
            # @import Framework; (tratamos como módulo)
            for mod in RE_OBJC_IMPORT_MOD.findall(text):
                imports[rel].add(f'@module:{mod}')
            # @class Foo, Bar;
            for line in RE_OBJC_CLASS_FWD.findall(text):
                for sym in [s.strip() for s in line.split(',')]:
                    uses[rel].add((sym, 'type'))

            # Usos (muito aproximados) - usar texto sem comentários
            for cls, sel in RE_OBJC_MSG_SEND_CLASS.findall(analysis_text):
                if cls not in COMMON_KEYWORDS:
                    uses[rel].add((cls, 'type'))
                    if sel not in COMMON_KEYWORDS:
                        uses[rel].add((f'{cls}.{sel}', 'call'))
            for obj, sel in RE_OBJC_MSG_SEND_OBJ.findall(analysis_text):
                # obj pode ser variável; registramos só o seletor se não for comum
                if sel not in COMMON_KEYWORDS:
                    # Só adicionar se for um seletor que parece específico
                    if len(sel) > 4 and not sel.startswith('set') and not sel.startswith('get'):
                        uses[rel].add((sel, 'call'))
            for t in RE_OBJC_TYPE_USAGE.findall(analysis_text):
                # Filtrar tipos comuns do Foundation/UIKit
                if t not in COMMON_KEYWORDS and not t.startswith('NS') and not t.startswith('UI'):
                    uses[rel].add((t, 'type'))
            for pr in RE_OBJC_PROTOCOL_USE.findall(analysis_text):
                if pr not in COMMON_KEYWORDS:
                    uses[rel].add((pr, 'proto'))
            for fn in RE_C_FUNC_CALL.findall(analysis_text):
                # Apenas funções do sistema com prefixos conhecidos
                uses[rel].add((fn, 'func'))

        else:  # Swift
            for mod in RE_SWIFT_IMPORT.findall(text):
                imports[rel].add(f'module:{mod}')
            # Usar texto sem comentários para análise de uso de símbolos
            for t, sel in RE_SWIFT_STATIC_CALL.findall(analysis_text):
                if t not in COMMON_KEYWORDS:
                    uses[rel].add((t, 'type'))
                    if sel not in COMMON_KEYWORDS:
                        uses[rel].add((f'{t}.{sel}', 'call'))
            for obj, sel in RE_SWIFT_INST_CALL.findall(analysis_text):
                # Ignorar métodos muito comuns
                if sel not in COMMON_KEYWORDS and len(sel) > 4:
                    # Só adicionar se for um método que parece específico
                    if not sel.startswith('set') and not sel.startswith('get'):
                        uses[rel].add((sel, 'call'))
            for t in RE_SWIFT_TYPE_ANNOT.findall(analysis_text):
                # Filtrar tipos básicos do Swift e classes base comuns
                if t not in COMMON_KEYWORDS and t not in {'String', 'Int', 'Bool', 'Double', 'Float', 'Any', 'AnyObject', 'Void', 'NSObject'}:
                    uses[rel].add((t, 'type'))
            for pr in RE_SWIFT_PROTO_CONF.findall(analysis_text):
                if pr not in COMMON_KEYWORDS and pr not in {'Codable', 'Equatable', 'Hashable', 'Comparable'}:
                    uses[rel].add((pr, 'proto'))

    # Resolver usos de símbolos para arquivos quando possível
    return imports, uses

def build_graph(root: Path, use_cache=True, ignore_paths=None, shallow=False):
    # Tentar usar cache se habilitado
    cache_dir = Path.home() / '.swift-dep-cache'
    cache_key = get_cache_key(root) if use_cache else None
    cache_file = cache_dir / f'{cache_key}.pkl' if cache_key else None
    
    if use_cache and cache_file and cache_file.exists():
        cached_data = load_cache(cache_file)
        if cached_data and 'graph' in cached_data:
            print('  Usando cache de análise anterior')
            return cached_data['graph']
    
    # Detectar bridging header se existir
    bridging_header = find_bridging_header(root)
    bridging_header_imports = set()
    bridging_header_files = set()  # Arquivos completos importados pelo bridging header
    if bridging_header:
        print(f'  Bridging header detectado: {bridging_header.name}')
        # Ler imports do bridging header
        try:
            bridging_content = read_text(bridging_header)
            # Coletar todos os arquivos disponíveis por basename
            all_files_by_basename = {}
            for f in iter_source_files(root, SUPPORTED, ignore_paths):
                rel = normalize_rel(root, f)
                all_files_by_basename.setdefault(f.name, set()).add(rel)
            
            for match in RE_IMPORT_LOCAL.findall(bridging_content) + RE_INCLUDE_LOCAL.findall(bridging_content):
                basename = Path(match).name
                bridging_header_imports.add(basename)
                # Resolver para arquivos completos
                for candidate in all_files_by_basename.get(basename, []):
                    bridging_header_files.add(candidate)
        except:
            pass
    
    # Parse xcconfig files se existirem
    xcconfig = parse_xcconfig_files(root)
    if xcconfig:
        print(f'  Encontradas {len(xcconfig)} configurações em .xcconfig files')
    
    symbols_declared, symbol_to_file = collect_declarations(root, ignore_paths)
    imports, uses = collect_imports_and_usages(root, symbol_to_file, ignore_paths)

    # Coletar extensões de arquivo para validação
    file_extensions = {}
    for f in iter_source_files(root, SUPPORTED, ignore_paths):
        rel = normalize_rel(root, f)
        file_extensions[rel] = f.suffix
    
    def is_valid_dependency(source_file: str, target_file: str) -> bool:
        """Valida se uma dependência é possível entre dois arquivos."""
        # Se algum dos arquivos é um módulo, sempre permitir
        if source_file.startswith(('module:', '@module:')) or target_file.startswith(('module:', '@module:')):
            return True
        
        source_ext = file_extensions.get(source_file, '')
        target_ext = file_extensions.get(target_file, '')
        
        # Swift pode importar Swift
        if source_ext == '.swift' and target_ext == '.swift':
            return True
        
        # ObjC pode importar ObjC
        if source_ext in OBJC_EXTS and target_ext in OBJC_EXTS:
            return True
        
        # Swift pode importar ObjC se o arquivo ObjC estiver no bridging header
        if source_ext == '.swift' and target_ext in OBJC_EXTS:
            target_name = Path(target_file).name
            return target_name in bridging_header_imports or bridging_header is not None
        
        # ObjC não pode importar Swift diretamente (precisaria de -Swift.h gerado)
        if source_ext in OBJC_EXTS and target_ext == '.swift':
            # Só permitir se houver evidência de uso do header Swift gerado
            # Por ora, bloquear essas dependências para evitar falsos positivos
            return False
        
        return True

    # Adjacência com rótulos de símbolos usados
    adj = defaultdict(lambda: defaultdict(set))

    if shallow:
        # Modo shallow: apenas dependências baseadas em símbolos efetivamente usados
        # NÃO incluir imports genéricos
        
        # Arestas apenas por uso de símbolos (se símbolo mapeia para um arquivo local)
        for a, usages in uses.items():
            for sym, kind in usages:
                # Símbolos com formato Classe.metodo → tentar mapear pela Classe
                target_file = None
                if '.' in sym:
                    base = sym.split('.', 1)[0]
                    target_file = symbol_to_file.get(base)
                else:
                    target_file = symbol_to_file.get(sym)
                if target_file and target_file != a:
                    # Validar se a dependência é possível
                    if is_valid_dependency(a, target_file):
                        label = f'{sym}[{kind}]'
                        adj[a][target_file].add(label)
        
        # IMPORTANTE: Para arquivos Swift, adicionar dependências dos símbolos usados
        # que vêm de arquivos ObjC importados pelo bridging header
        if bridging_header_files:
            for a in uses.keys():
                # Verificar se é um arquivo Swift
                if file_extensions.get(a, '') == '.swift':
                    # Para cada símbolo usado pelo arquivo Swift
                    for sym, kind in uses[a]:
                        # Extrair o nome base do símbolo
                        base_sym = sym.split('.', 1)[0] if '.' in sym else sym
                        # Verificar se o símbolo está declarado em algum arquivo do bridging header
                        for bridging_file in bridging_header_files:
                            if base_sym in symbols_declared.get(bridging_file, set()):
                                # Adicionar dependência para o arquivo do bridging header
                                label = f'{sym}[{kind}]'
                                adj[a][bridging_file].add(label)
        
        # Adicionar módulos externos apenas se houver uso direto
        for a, imported in imports.items():
            for item in imported:
                if item.startswith('@module:') or item.startswith('module:'):
                    # Verificar se há algum uso de símbolo que poderia vir deste módulo
                    # Por ora, incluir apenas se explicitamente importado e usado
                    if any(sym for sym, _ in uses.get(a, []) if '.' not in sym):
                        adj[a][item].add('<module-import>')
    else:
        # Modo normal: incluir imports e usos
        
        # Arestas por imports diretos resolvidos para arquivo
        for a, imported in imports.items():
            for item in imported:
                if item.startswith('@module:') or item.startswith('module:'):
                    # Módulo externo: podemos manter como nó "virtual" de módulo
                    adj[a][item].add('<module-import>')
                else:
                    adj[a][item].add('<import>')

        # Arestas por uso de símbolos (se símbolo mapeia para um arquivo local)
        for a, usages in uses.items():
            for sym, kind in usages:
                # Símbolos com formato Classe.metodo → tentar mapear pela Classe
                target_file = None
                if '.' in sym:
                    base = sym.split('.', 1)[0]
                    target_file = symbol_to_file.get(base)
                else:
                    target_file = symbol_to_file.get(sym)
                if target_file and target_file != a:
                    # Validar se a dependência é possível
                    if is_valid_dependency(a, target_file):
                        label = f'{sym}'
                        adj[a][target_file].add(label)

    # Normalizar sets para listas ordenadas
    graph = {a: {b: sorted(list(labels)) for b, labels in bmap.items()}
             for a, bmap in adj.items()}
    
    # Salvar no cache se habilitado
    if use_cache and cache_file:
        save_cache(cache_file, {'graph': graph})
    
    return graph

# Function removed - now integrated into main()

def detect_cycles(graph: dict) -> list:
    """
    Detecta ciclos no grafo usando DFS.
    Retorna lista de ciclos encontrados.
    """
    def dfs_cycle(node, visited, rec_stack, path, cycles):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        
        for neighbor in graph.get(node, {}):
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
    
    for node in graph:
        if node not in visited:
            rec_stack = set()
            path = []
            dfs_cycle(node, visited, rec_stack, path, cycles)
    
    # Remover ciclos duplicados
    unique_cycles = []
    seen = set()
    for cycle in cycles:
        # Normalizar ciclo para comparação
        normalized = tuple(sorted(cycle[:-1]))  # Excluir último elemento (duplicado do primeiro)
        if normalized not in seen:
            seen.add(normalized)
            unique_cycles.append(cycle)
    
    return unique_cycles

def find_all_paths(graph: dict, start: str, end: str, max_depth: int = 10) -> list:
    """
    Encontra todos os caminhos entre dois vértices no grafo usando BFS.
    Os caminhos mais curtos são retornados primeiro.
    
    Args:
        graph: Grafo de dependências
        start: Vértice de origem
        end: Vértice de destino
        max_depth: Profundidade máxima para evitar loops infinitos
    
    Returns:
        Lista de caminhos ordenados por comprimento (mais curtos primeiro)
    """
    from collections import deque
    
    if start == end:
        return [[start]]
    
    # Lista para armazenar todos os caminhos encontrados
    all_paths = []
    
    # Fila para BFS: cada elemento é (nó_atual, caminho_até_aqui)
    queue = deque([(start, [start])])
    
    # Conjunto de caminhos já processados para evitar duplicatas
    visited_paths = set()
    
    while queue:
        current, path = queue.popleft()
        
        # Se o caminho excede a profundidade máxima, pular
        if len(path) > max_depth:
            continue
        
        # Explorar vizinhos
        for neighbor in graph.get(current, {}):
            # Evitar ciclos no caminho atual
            if neighbor not in path:
                new_path = path + [neighbor]
                
                # Converter caminho para tupla para poder adicionar ao set
                path_tuple = tuple(new_path)
                
                # Se já processamos este caminho exato, pular
                if path_tuple in visited_paths:
                    continue
                
                visited_paths.add(path_tuple)
                
                if neighbor == end:
                    # Encontrou um caminho completo
                    all_paths.append(new_path)
                else:
                    # Adicionar à fila para continuar explorando
                    queue.append((neighbor, new_path))
    
    # Os caminhos já estão naturalmente ordenados por comprimento devido ao BFS
    return all_paths

def format_path_with_labels(path: list, graph: dict) -> str:
    """
    Formata um caminho incluindo os labels das arestas (métodos/símbolos usados).
    
    Args:
        path: Lista de vértices formando um caminho
        graph: Grafo com labels nas arestas
    
    Returns:
        String formatada representando o caminho com labels
    """
    if not path:
        return ""
    
    formatted = []
    for i in range(len(path) - 1):
        source = path[i]
        target = path[i + 1]
        
        # Obter labels da aresta
        labels = graph.get(source, {}).get(target, [])
        
        # Filtrar labels relevantes (métodos/funções)
        relevant_labels = []
        for label in labels:
            if not label.startswith('<') and label not in ['<import>', '<module-import>']:
                relevant_labels.append(label)
        
        # Formatar o passo
        if relevant_labels:
            # Usar o primeiro label relevante (geralmente o mais importante)
            formatted.append(f"{source} -> {relevant_labels[0]} -> {target}")
        else:
            formatted.append(f"{source} -> {target}")
    
    return "\n".join(formatted)

def find_orphan_files(graph: dict, root: Path, ignore_paths=None) -> list:
    """
    Encontra arquivos que existem no projeto mas não são referenciados.
    """
    # Coletar todos os arquivos do projeto
    all_files = set()
    for f in iter_source_files(root, SUPPORTED, ignore_paths):
        rel = normalize_rel(root, f)
        all_files.add(rel)
    
    # Coletar arquivos referenciados (que aparecem como nós ou são referenciados)
    referenced = set(graph.keys())
    for node, edges in graph.items():
        referenced.update(edges.keys())
    
    # Filtrar apenas arquivos locais (não módulos)
    referenced = {f for f in referenced if not (f.startswith('module:') or f.startswith('@module:'))}
    
    # Arquivos órfãos são os que existem mas não são referenciados
    orphans = all_files - referenced
    
    return sorted(orphans)

def calculate_metrics(graph: dict) -> dict:
    """
    Calcula métricas de complexidade do grafo.
    """
    metrics = {}
    
    # Métricas básicas
    metrics['total_files'] = len(graph)
    metrics['total_edges'] = sum(len(edges) for edges in graph.values())
    
    # Calcular coupling (acoplamento)
    afferent_coupling = defaultdict(int)  # Quantos dependem de mim
    efferent_coupling = defaultdict(int)  # De quantos eu dependo
    
    for source, targets in graph.items():
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

def load_config(config_file: str) -> dict:
    """
    Carrega configuração de arquivo .swiftdeprc
    """
    config = {
        'ignore_patterns': [],
        'custom_extensions': [],
        'cache_enabled': True,
        'max_depth': None
    }
    
    if not config_file:
        # Procurar .swiftdeprc no diretório atual ou home
        for path in [Path.cwd() / '.swiftdeprc', Path.home() / '.swiftdeprc']:
            if path.exists():
                config_file = str(path)
                break
    
    if config_file and Path(config_file).exists():
        try:
            with open(config_file, 'r') as f:
                import configparser
                parser = configparser.ConfigParser()
                parser.read_string('[DEFAULT]\n' + f.read())
                
                if 'ignore_patterns' in parser['DEFAULT']:
                    config['ignore_patterns'] = parser['DEFAULT']['ignore_patterns'].split(',')
                if 'custom_extensions' in parser['DEFAULT']:
                    config['custom_extensions'] = parser['DEFAULT']['custom_extensions'].split(',')
                if 'cache_enabled' in parser['DEFAULT']:
                    config['cache_enabled'] = parser['DEFAULT'].getboolean('cache_enabled')
                if 'max_depth' in parser['DEFAULT']:
                    config['max_depth'] = parser['DEFAULT'].getint('max_depth')
                
                print(f'  Configuração carregada de {config_file}')
        except Exception as e:
            print(f'  Aviso: Erro ao carregar configuração: {e}')
    
    return config

def create_test_project():
    """
    Cria uma estrutura de projeto Xcode de teste com cenários complexos para testes diversos:
    - Dependências circulares
    - Arquivos órfãos
    - Múltiplos caminhos entre arquivos
    - Dependências profundas
    - Bridging entre Swift e Objective-C
    """
    test_root = Path.cwd() / 'test_project'
    
    print('🔨 Criando projeto de teste complexo em test_project/')
    print('  Características do projeto de teste:')
    print('  • Ciclos de dependência (A→B→C→A)')
    print('  • Arquivos órfãos isolados')
    print('  • Múltiplos caminhos entre arquivos')
    print('  • Dependências profundas (5+ níveis)')
    print('  • Integração Swift/Objective-C')
    
    # Estrutura complexa de projeto iOS
    structure = {
        'MyApp': {
            'AppDelegate.swift': '''import UIKit
import CoreData

@main
class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?
    private let analyticsManager = AnalyticsManager.shared
    
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        let mainViewController = MainViewController()
        window?.rootViewController = mainViewController
        
        // Inicializar analytics
        analyticsManager.trackAppLaunch()
        
        return true
    }
}''',
            'SceneDelegate.swift': '''import UIKit

class SceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?
    private let router = AppRouter.shared
    
    func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options connectionOptions: UIScene.ConnectionOptions) {
        guard let windowScene = (scene as? UIWindowScene) else { return }
        window = UIWindow(windowScene: windowScene)
        window?.rootViewController = router.initialViewController()
        window?.makeKeyAndVisible()
    }
}''',
        },
        'MyApp/Controllers': {
            'MainViewController.swift': '''import UIKit

class MainViewController: UIViewController {
    private let networkManager = NetworkManager.shared
    private let dataManager = DataManager()
    private let router = AppRouter.shared
    
    override func viewDidLoad() {
        super.viewDidLoad()
        setupUI()
        loadData()
        
        // Múltiplos caminhos: MainViewController pode acessar UserProfile de várias formas
        // Caminho 1: via DetailViewController
        // Caminho 2: via LoginViewController -> UserManager
        // Caminho 3: via SettingsViewController
    }
    
    private func setupUI() {
        let detailVC = DetailViewController()
        addChild(detailVC)
    }
    
    private func loadData() {
        networkManager.fetchData { [weak self] result in
            self?.dataManager.processData(result)
        }
    }
    
    private func showSettings() {
        let settingsVC = SettingsViewController()
        navigationController?.pushViewController(settingsVC, animated: true)
    }
}''',
            'DetailViewController.swift': '''import UIKit

class DetailViewController: UIViewController {
    private let viewModel = DetailViewModel()
    private let userProfileManager = UserProfileManager.shared
    
    override func viewDidLoad() {
        super.viewDidLoad()
        viewModel.delegate = self
        loadUserProfile()
    }
    
    private func loadUserProfile() {
        // Caminho para UserProfile
        userProfileManager.loadProfile()
    }
}

extension DetailViewController: DetailViewModelDelegate {
    func didUpdateData() {
        // Update UI
        // CICLO: DetailViewController -> DetailViewModel -> DetailViewController
        viewModel.refreshData()
    }
}''',
            'LoginViewController.m': '''#import "LoginViewController.h"
#import "UserManager.h"
#import "NetworkManager.h"
#import "CycleClassA.h"

@interface LoginViewController ()
@property (nonatomic, strong) UserManager *userManager;
@property (nonatomic, strong) CycleClassA *cycleHelper;
@end

@implementation LoginViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    self.userManager = [[UserManager alloc] init];
    self.cycleHelper = [[CycleClassA alloc] init];
    [[NetworkManager sharedInstance] checkConnection];
}

- (void)loginUser {
    [self.userManager authenticateUser:@"user" password:@"pass"];
    // Outro caminho para UserProfile
    [self.userManager loadUserProfile];
}

@end''',
            'LoginViewController.h': '''#import <UIKit/UIKit.h>

@interface LoginViewController : UIViewController

- (void)loginUser;

@end''',
        },
        'MyApp/Models': {
            'User.swift': '''import Foundation

struct User: Codable {
    let id: Int
    let name: String
    let email: String
    
    var displayName: String {
        return name.isEmpty ? email : name
    }
}''',
            'DataManager.swift': '''import Foundation
import CoreData

class DataManager {
    private let coreDataStack = CoreDataStack()
    
    func processData(_ data: Any) {
        // Process and save data
        coreDataStack.saveContext()
    }
    
    func fetchUsers() -> [User] {
        return []
    }
}''',
            'Product.m': '''#import "Product.h"

@implementation Product

- (instancetype)initWithName:(NSString *)name price:(double)price {
    self = [super init];
    if (self) {
        _name = name;
        _price = price;
    }
    return self;
}

- (NSString *)formattedPrice {
    return [NSString stringWithFormat:@"$%.2f", self.price];
}

@end''',
            'Product.h': '''#import <Foundation/Foundation.h>

@interface Product : NSObject

@property (nonatomic, strong) NSString *name;
@property (nonatomic, assign) double price;

- (instancetype)initWithName:(NSString *)name price:(double)price;
- (NSString *)formattedPrice;

@end''',
        },
        'MyApp/ViewModels': {
            'DetailViewModel.swift': '''import Foundation

protocol DetailViewModelDelegate: AnyObject {
    func didUpdateData()
}

class DetailViewModel {
    weak var delegate: DetailViewModelDelegate?
    private let networkManager = NetworkManager.shared
    
    func loadDetails() {
        networkManager.fetchDetails { [weak self] _ in
            self?.delegate?.didUpdateData()
        }
    }
    
    func refreshData() {
        // CICLO: Chamado por DetailViewController que é o delegate
        loadDetails()
    }
}''',
        },
        'MyApp/Controllers/Settings': {
            'SettingsViewController.swift': '''import UIKit

class SettingsViewController: UIViewController {
    private let userProfileManager = UserProfileManager.shared
    private let themeManager = ThemeManager.shared
    
    override func viewDidLoad() {
        super.viewDidLoad()
        // Terceiro caminho para UserProfile
        userProfileManager.updateSettings()
    }
    
    func changeTheme() {
        themeManager.toggleTheme()
    }
}''',
            'ThemeManager.swift': '''import UIKit

class ThemeManager {
    static let shared = ThemeManager()
    private let preferencesManager = PreferencesManager.shared
    
    private init() {}
    
    func toggleTheme() {
        // CICLO PROFUNDO: ThemeManager -> PreferencesManager -> NotificationCenter -> ThemeManager
        preferencesManager.updateThemePreference()
    }
}''',
            'PreferencesManager.swift': '''import Foundation

class PreferencesManager {
    static let shared = PreferencesManager()
    private let notificationCenter = AppNotificationCenter.shared
    
    private init() {}
    
    func updateThemePreference() {
        // Parte do ciclo
        notificationCenter.postThemeChanged()
    }
}''',
            'AppNotificationCenter.swift': '''import Foundation

class AppNotificationCenter {
    static let shared = AppNotificationCenter()
    
    private init() {}
    
    func postThemeChanged() {
        // COMPLETA O CICLO: volta para ThemeManager
        ThemeManager.shared.toggleTheme()
    }
}''',
        },
        'MyApp/Services': {
            'NetworkManager.swift': '''import Foundation

class NetworkManager {
    static let shared = NetworkManager()
    
    private init() {}
    
    func fetchData(completion: @escaping (Result<Data, Error>) -> Void) {
        // Network implementation
    }
    
    func fetchDetails(completion: @escaping (Result<Any, Error>) -> Void) {
        // Fetch details
    }
}''',
            'UserManager.h': '''#import <Foundation/Foundation.h>

@interface UserManager : NSObject

- (void)authenticateUser:(NSString *)username password:(NSString *)password;
- (BOOL)isUserLoggedIn;
- (void)loadUserProfile;

@end''',
            'UserManager.m': '''#import "UserManager.h"

@implementation UserManager

- (void)authenticateUser:(NSString *)username password:(NSString *)password {
    // Authentication logic
}

- (BOOL)isUserLoggedIn {
    return NO;
}

- (void)loadUserProfile {
    // Carrega perfil do usuário
}

@end''',
            'UserProfileManager.swift': '''import Foundation

class UserProfileManager {
    static let shared = UserProfileManager()
    private let analyticsManager = AnalyticsManager.shared
    
    private init() {}
    
    func loadProfile() {
        // Múltiplos caminhos chegam aqui:
        // 1. DetailViewController -> UserProfileManager
        // 2. LoginViewController -> UserManager -> UserProfileManager
        // 3. SettingsViewController -> UserProfileManager
        analyticsManager.trackProfileLoad()
    }
    
    func updateSettings() {
        // Atualiza configurações do perfil
    }
}''',
            'AnalyticsManager.swift': '''import Foundation

class AnalyticsManager {
    static let shared = AnalyticsManager()
    
    private init() {}
    
    func trackAppLaunch() {
        // Track app launch
    }
    
    func trackProfileLoad() {
        // Track profile load
    }
}''',
            'AppRouter.swift': '''import UIKit

class AppRouter {
    static let shared = AppRouter()
    
    private init() {}
    
    func initialViewController() -> UIViewController {
        return MainViewController()
    }
}''',
            'NetworkManager.h': '''#import <Foundation/Foundation.h>

@interface NetworkManager : NSObject

+ (instancetype)sharedInstance;
- (void)checkConnection;

@end''',
            'NetworkManager.m': '''#import "NetworkManager.h"

@implementation NetworkManager

+ (instancetype)sharedInstance {
    static NetworkManager *instance = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        instance = [[NetworkManager alloc] init];
    });
    return instance;
}

- (void)checkConnection {
    // Check network connection
}

@end''',
        },
        'MyApp/Utils': {
            'CoreDataStack.swift': '''import CoreData

class CoreDataStack {
    lazy var persistentContainer: NSPersistentContainer = {
        let container = NSPersistentContainer(name: "MyApp")
        container.loadPersistentStores { _, error in
            if let error = error {
                fatalError("Core Data failed: \\(error)")
            }
        }
        return container
    }()
    
    func saveContext() {
        let context = persistentContainer.viewContext
        if context.hasChanges {
            try? context.save()
        }
    }
}''',
            'Extensions.swift': '''import UIKit

extension UIView {
    func addSubviews(_ views: UIView...) {
        views.forEach { addSubview($0) }
    }
}

extension String {
    var localized: String {
        return NSLocalizedString(self, comment: "")
    }
}''',
            'Constants.h': '''#ifndef Constants_h
#define Constants_h

static NSString * const kAPIBaseURL = @"https://api.example.com";
static NSString * const kUserDefaultsKey = @"UserDefaults";

#endif /* Constants_h */''',
        },
        'MyApp/Resources': {
            'Info.plist': '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>MyApp</string>
</dict>
</plist>''',
        },
        'MyAppTests': {
            'MyAppTests.swift': '''import XCTest
@testable import MyApp

class MyAppTests: XCTestCase {
    func testUser() {
        let user = User(id: 1, name: "Test", email: "test@example.com")
        XCTAssertEqual(user.displayName, "Test")
    }
}''',
            'NetworkTests.m': '''#import <XCTest/XCTest.h>
#import "NetworkManager.h"

@interface NetworkTests : XCTestCase
@end

@implementation NetworkTests

- (void)testSharedInstance {
    NetworkManager *instance1 = [NetworkManager sharedInstance];
    NetworkManager *instance2 = [NetworkManager sharedInstance];
    XCTAssertEqual(instance1, instance2);
}

@end''',
        },
        'Pods/Alamofire/Source': {
            'Alamofire.swift': '''// Mock Alamofire
public class Alamofire {
    public static func request(_ url: String) -> DataRequest {
        return DataRequest()
    }
}

public class DataRequest {
    public func response(completionHandler: @escaping () -> Void) {
        completionHandler()
    }
}''',
        },
        'Pods/SDWebImage': {
            'SDWebImage.h': '''// Mock SDWebImage
@interface SDWebImage : NSObject
+ (instancetype)sharedInstance;
@end''',
        },
        'MyApp/Orphans': {
            'OrphanFile1.swift': '''import Foundation

// ARQUIVO ÓRFÃO: Não é importado ou usado por ninguém
class OrphanClass1 {
    func unusedMethod() {
        print("I am never called")
    }
}''',
            'OrphanFile2.m': '''#import <Foundation/Foundation.h>

// ARQUIVO ÓRFÃO: Código legado esquecido
@interface OrphanClass2 : NSObject
- (void)deprecatedMethod;
@end

@implementation OrphanClass2
- (void)deprecatedMethod {
    NSLog(@"This is deprecated and unused");
}
@end''',
            'OrphanFile3.swift': '''import UIKit

// ARQUIVO ÓRFÃO: Feature abandonada
class AbandonedFeatureViewController: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()
        // Feature that was never completed
    }
}''',
            'UnusedUtility.h': '''#ifndef UnusedUtility_h
#define UnusedUtility_h

// ARQUIVO ÓRFÃO: Header sem implementação e sem uso
@interface UnusedUtility : NSObject
+ (void)doNothing;
@end

#endif''',
        },
        'MyApp/Cycles': {
            'CycleClassA.h': '''#import <Foundation/Foundation.h>

@class CycleClassB;

@interface CycleClassA : NSObject
@property (nonatomic, strong) CycleClassB *classB;
- (void)methodA;
@end''',
            'CycleClassA.m': '''#import "CycleClassA.h"
#import "CycleClassB.h"
#import "CycleClassC.h"

@implementation CycleClassA

- (void)methodA {
    [self.classB methodB];
    // CICLO: A -> B -> C -> A
    CycleClassC *c = [[CycleClassC alloc] init];
    [c methodC];
}

@end''',
            'CycleClassB.h': '''#import <Foundation/Foundation.h>

@class CycleClassC;

@interface CycleClassB : NSObject
@property (nonatomic, strong) CycleClassC *classC;
- (void)methodB;
@end''',
            'CycleClassB.m': '''#import "CycleClassB.h"
#import "CycleClassC.h"

@implementation CycleClassB

- (void)methodB {
    [self.classC methodC];
}

@end''',
            'CycleClassC.h': '''#import <Foundation/Foundation.h>

@class CycleClassA;

@interface CycleClassC : NSObject
@property (nonatomic, strong) CycleClassA *classA;
- (void)methodC;
@end''',
            'CycleClassC.m': '''#import "CycleClassC.h"
#import "CycleClassA.h"

@implementation CycleClassC

- (void)methodC {
    // COMPLETA O CICLO: C -> A
    [self.classA methodA];
}

@end''',
        },
        'MyApp/DeepDependency': {
            'Level1.swift': '''import Foundation

class Level1 {
    func start() {
        let level2 = Level2()
        level2.process()
    }
}''',
            'Level2.swift': '''import Foundation

class Level2 {
    func process() {
        let level3 = Level3()
        level3.compute()
    }
}''',
            'Level3.swift': '''import Foundation

class Level3 {
    func compute() {
        let level4 = Level4()
        level4.analyze()
    }
}''',
            'Level4.swift': '''import Foundation

class Level4 {
    func analyze() {
        let level5 = Level5()
        level5.execute()
    }
}''',
            'Level5.swift': '''import Foundation

class Level5 {
    func execute() {
        let level6 = Level6()
        level6.finalize()
    }
}''',
            'Level6.swift': '''import Foundation

class Level6 {
    func finalize() {
        // Fim da cadeia profunda
        print("Deep dependency chain complete")
    }
}''',
        },
        '': {  # Arquivos na raiz
            'Podfile': '''platform :ios, '14.0'

target 'MyApp' do
  use_frameworks!
  
  pod 'Alamofire'
  pod 'SDWebImage'
end''',
            'MyApp-Bridging-Header.h': '''#import "LoginViewController.h"
#import "UserManager.h"
#import "NetworkManager.h"
#import "Product.h"
#import "Constants.h"
#import "CycleClassA.h"
#import "CycleClassB.h"
#import "CycleClassC.h"''',
            'MyApp.xcodeproj/project.pbxproj': '''// Simplified project file
// This would normally be much larger''',
        }
    }
    
    # Criar estrutura de diretórios e arquivos
    for dir_path, files in structure.items():
        if dir_path:
            dir_full_path = test_root / dir_path
        else:
            dir_full_path = test_root
        
        dir_full_path.mkdir(parents=True, exist_ok=True)
        
        for filename, content in files.items():
            file_path = dir_full_path / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding='utf-8')
    
    print(f'✅ Projeto de teste complexo criado com sucesso em: {test_root}')
    print(f'   - {len([f for d in structure.values() for f in d.items()])} arquivos criados')
    print(f'\n📊 Cenários de teste incluídos:')
    print(f'   • Ciclos de dependência:')
    print(f'     - DetailViewController ↔ DetailViewModel (Swift)')
    print(f'     - ThemeManager → PreferencesManager → AppNotificationCenter → ThemeManager')
    print(f'     - CycleClassA → CycleClassB → CycleClassC → CycleClassA (Objective-C)')
    print(f'   • Arquivos órfãos: 4 arquivos isolados em MyApp/Orphans/')
    print(f'   • Múltiplos caminhos para UserProfileManager:')
    print(f'     - Via DetailViewController')
    print(f'     - Via LoginViewController → UserManager')
    print(f'     - Via SettingsViewController')
    print(f'   • Cadeia profunda: Level1 → Level2 → ... → Level6 (6 níveis)')
    print(f'   • Integração Swift/Objective-C via bridging header')
    print(f'\n🧪 Comandos úteis para testar:')
    print(f'   python3 code_depth_graph.py test_project --detect-cycles')
    print(f'   python3 code_depth_graph.py test_project --find-orphans')
    print(f'   python3 code_depth_graph.py test_project/MyApp/Controllers/MainViewController.swift --closure --showPath MyApp/Services/UserProfileManager.swift')
    print(f'   python3 code_depth_graph.py test_project/MyApp/DeepDependency/Level1.swift --closure')
    
    return test_root

def transitive_closure(graph: dict, start: str, include_modules=False, shallow_mode=False, symbols_declared=None, symbol_to_file=None, uses=None):
    """
    Fecho transitivo direto a partir de 'start'.
    Retorna todos os arquivos que 'start' depende (direta ou indiretamente).
    Por padrão, ignora nós de módulos externos (module:..., @module:...).
    
    Se shallow_mode=True, usa o grafo já construído no modo shallow (que já tem apenas símbolos usados).
    """
    def is_module(n: str) -> bool:
        return n.startswith('module:') or n.startswith('@module:')

    # Tanto no modo shallow quanto normal, usar o grafo já construído
    # (que foi construído respeitando o modo shallow quando aplicável)
    visited = set()
    q = deque([start])
    while q:
        u = q.popleft()
        if u in visited:
            continue
        visited.add(u)
        for v in graph.get(u, {}):
            if not include_modules and is_module(v):
                continue
            if v not in visited:
                q.append(v)
    visited.discard(start)
    return sorted(visited)

def main():
    ap = argparse.ArgumentParser(description="Grafo de dependências (ObjC/ObjC++/Swift) com rótulos de uso.")
    ap.add_argument('path', nargs='?', default='test_project',
                    help='Arquivo ou diretório do projeto (padrão: test_project)')
    ap.add_argument('--test', action='store_true',
                    help='Criar projeto de teste em test_project/')
    ap.add_argument('--root-exts', default=None,
                    help='Lista de extensões consideradas (padrão: .m,.mm,.swift,.h,.hh)')
    ap.add_argument('--no-closure', action='store_true', 
                    help='Desabilitar cálculo de fecho transitivo (padrão: habilitado para arquivos)')
    ap.add_argument('--closure-file', default=None, 
                    help='Arquivo específico para calcular fecho transitivo (mantido para compatibilidade)')
    ap.add_argument('--include-modules', action='store_true', help='Incluir módulos externos no fecho transitivo')
    ap.add_argument('--output-dir', default=None, help='Diretório para salvar os arquivos de saída')
    ap.add_argument('--writeCode', action='store_true', help='Gerar arquivo files_code.txt com o código de todos os arquivos do fecho transitivo')
    ap.add_argument('--mermaid', action='store_true', help='Gerar diagrama no formato Mermaid (.mmd)')
    ap.add_argument('--no-cache', action='store_true', help='Desabilitar uso de cache')
    ap.add_argument('--csv', action='store_true', help='Exportar grafo e métricas para CSV')
    ap.add_argument('--detect-cycles', action='store_true', help='Detectar dependências circulares')
    ap.add_argument('--find-orphans', action='store_true', help='Encontrar arquivos órfãos (não referenciados)')
    ap.add_argument('--config', default=None, help='Arquivo de configuração (.swiftdeprc)')
    ap.add_argument('--ignore', action='append', help='Paths a ignorar (ex: --ignore Pods --ignore .build)')
    ap.add_argument('--extended', action='store_true', help='Análise estendida: inclui todos imports e símbolos (padrão: análise superficial)')
    ap.add_argument('--direct-deps-only', action='store_true', help='Mostrar apenas dependências diretas do arquivo alvo')
    ap.add_argument('--showPath', default=None, help='Arquivo de destino para mostrar caminhos (funciona com closure automático)')
    ap.add_argument('--clear', action='store_true', help='Limpar toda a pasta output')
    args = ap.parse_args()

    # Se --clear foi especificado, limpar pasta output e sair
    if args.clear:
        import shutil
        output_dir = Path.cwd() / 'output'
        if output_dir.exists():
            shutil.rmtree(output_dir)
            print('🧹 Pasta output removida com sucesso')
        else:
            print('ℹ️  Pasta output não existe')
        return

    # Se --test foi especificado, criar projeto de teste e sair
    if args.test:
        create_test_project()
        return
    
    # Carregar configuração se especificada
    config = load_config(args.config)
    
    # Se o path padrão (test_project) não existe, criar automaticamente
    input_path = Path(args.path).resolve()
    if args.path == 'test_project' and not input_path.exists():
        print('📦 Projeto test_project não encontrado. Criando automaticamente...\n')
        create_test_project()
        print('\n' + '='*60 + '\n')
    
    # Verificar se o path existe agora
    input_path = Path(args.path).resolve()
    if not input_path.exists():
        print(f'Erro: caminho não encontrado: {input_path}')
        print(f'\nDica: Use --test para criar um projeto de teste')
        return

    # Determinar a raiz do projeto e o arquivo alvo (se aplicável)
    if input_path.is_file():
        root = find_xcode_project_root(input_path)
        target_file = input_path
        print(f'Arquivo detectado: {input_path.name}')
        print(f'Raiz do projeto detectada: {root}')
    else:
        root = input_path
        target_file = None
        print(f'Usando diretório como raiz do projeto: {root}')

    global OBJC_EXTS, SWIFT_EXTS, SUPPORTED
    if args.root_exts:
        lst = [s.strip() for s in args.root_exts.split(',') if s.strip()]
        SUPPORTED = set(lst)
    elif config['custom_extensions']:
        SUPPORTED = SUPPORTED | set(config['custom_extensions'])

    # Preparar lista de paths a ignorar
    ignore_paths = args.ignore if args.ignore else []
    if ignore_paths:
        print(f'\nIgnorando paths: {", ".join(ignore_paths)}')
    
    print('\nAnalisando projeto...')
    # Shallow é agora o padrão, extended precisa ser explicitamente solicitado
    use_shallow = not args.extended
    if use_shallow:
        print('  Modo shallow (padrão): analisando apenas símbolos diretamente usados')
    else:
        print('  Modo extended: incluindo todos imports e símbolos')
    graph = build_graph(root, use_cache=not args.no_cache, ignore_paths=ignore_paths, shallow=use_shallow)
    
    # Determinar o diretório de saída
    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
    else:
        # Sempre usar a pasta output no diretório atual
        base_output_dir = Path.cwd() / 'output'
        if input_path.is_file():
            # Se é um arquivo, criar subpasta com o nome do arquivo (sem extensão)
            output_dir = base_output_dir / input_path.stem
        else:
            # Se é um diretório, usar o nome do diretório
            output_dir = base_output_dir / root.name
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Salvar outputs no diretório especificado
    json_path = output_dir / 'graph.json'
    dot_path = output_dir / 'graph.dot'
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    
    with open(dot_path, 'w', encoding='utf-8') as f:
        f.write('digraph G {\n')
        f.write('  rankdir=LR;\n')
        f.write('  node [shape=box, fontname="Helvetica"];\n')
        # Declarar nós
        nodes = set(graph.keys())
        for a, bmap in graph.items():
            nodes.update(bmap.keys())
        for n in sorted(nodes):
            safe = n.replace('"', r'\"')
            f.write(f'  "{safe}";\n')
        # Arestas
        for a, bmap in graph.items():
            for b, labels in bmap.items():
                label = ', '.join(labels[:6])  # limitar rótulo para legibilidade
                if len(labels) > 6:
                    label += ', …'
                sa = a.replace('"', r'\"')
                sb = b.replace('"', r'\"')
                sl = label.replace('"', r'\"')
                f.write(f'  "{sa}" -> "{sb}" [label="{sl}"];\n')
        f.write('}\n')
    
    # Gerar formato Mermaid se solicitado
    if args.mermaid:
        mermaid_path = output_dir / 'graph.mmd'
        with open(mermaid_path, 'w', encoding='utf-8') as f:
            f.write('graph LR\n')
            # Declarar nós com IDs seguros
            node_ids = {}
            for i, n in enumerate(sorted(nodes)):
                node_id = f'N{i}'
                node_ids[n] = node_id
                # Simplificar nome para exibição
                display_name = n.split('/')[-1] if '/' in n else n
                f.write(f'    {node_id}["{display_name}"]\n')
            # Arestas
            for a, bmap in graph.items():
                if a in node_ids:
                    for b, labels in bmap.items():
                        if b in node_ids:
                            # Simplificar rótulo para Mermaid
                            label = labels[0] if labels else ''
                            if label and not label.startswith('<'):
                                f.write(f'    {node_ids[a]} -->|{label}| {node_ids[b]}\n')
                            else:
                                f.write(f'    {node_ids[a]} --> {node_ids[b]}\n')
        print(f'  - {mermaid_path}')
    
    # Export CSV se solicitado
    if args.csv:
        csv_path = output_dir / 'graph.csv'
        metrics_csv_path = output_dir / 'metrics.csv'
        
        # Exportar grafo para CSV
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Source', 'Target', 'Labels'])
            for source, targets in graph.items():
                for target, labels in targets.items():
                    writer.writerow([source, target, '; '.join(labels)])
        
        # Calcular e exportar métricas
        metrics = calculate_metrics(graph)
        with open(metrics_csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Metric', 'Value'])
            writer.writerow(['Total Files', metrics['total_files']])
            writer.writerow(['Total Edges', metrics['total_edges']])
            writer.writerow(['Average Dependencies', f"{metrics['avg_dependencies']:.2f}"])
            writer.writerow(['', ''])
            writer.writerow(['Most Depended On Files', 'Dependency Count'])
            for file, count in metrics['most_depended_on']:
                writer.writerow([file, count])
            writer.writerow(['', ''])
            writer.writerow(['Files with Most Dependencies', 'Count'])
            for file, count in metrics['most_dependencies']:
                writer.writerow([file, count])
        
        print(f'  - {csv_path}')
        print(f'  - {metrics_csv_path}')
    
    print(f'\nGrafo salvo em:')
    print(f'  - {json_path}')
    print(f'  - {dot_path}')

    # Calcular fecho transitivo (padrão para arquivos, a menos que --no-closure seja usado)
    closure_target = None
    # Se é um arquivo e não foi desabilitado o closure
    if target_file and not args.no_closure:
        closure_target = normalize_rel(root, target_file)
    elif args.closure_file:
        closure_target = args.closure_file
    
    # Se --showPath foi especificado, encontrar caminhos entre dois arquivos
    if closure_target and args.showPath:
        source_file = closure_target
        
        # Normalizar o caminho de destino para o formato relativo usado no grafo
        target_path = Path(args.showPath)
        if target_path.is_absolute():
            try:
                target_path_file = str(target_path.relative_to(root))
            except ValueError:
                # Se o caminho não está dentro da raiz, usar como está
                target_path_file = args.showPath
        else:
            target_path_file = args.showPath
        
        # Verificar se ambos os arquivos existem no grafo
        all_nodes = set(graph.keys())
        for adj in graph.values():
            all_nodes.update(adj.keys())
        
        if source_file not in all_nodes:
            print(f"\nErro: arquivo de origem '{source_file}' não encontrado no grafo")
            return
        
        if target_path_file not in all_nodes:
            print(f"\nErro: arquivo de destino '{target_path_file}' não encontrado no grafo")
            return
        
        print(f'\nProcurando caminhos de {source_file} para {target_path_file}...')
        
        # Encontrar todos os caminhos
        paths = find_all_paths(graph, source_file, target_path_file)
        
        if not paths:
            print(f'\nNenhum caminho encontrado de {source_file} para {target_path_file}')
        else:
            print(f'\nEncontrados {len(paths)} caminho(s):')
            
            # Criar arquivo de saída
            path_output_file = output_dir / f'path_{Path(source_file).stem}_{Path(target_path_file).stem}.txt'
            
            with open(path_output_file, 'w', encoding='utf-8') as f:
                f.write(f'Caminhos de {source_file} para {target_path_file}\n')
                f.write(f'Total de caminhos encontrados: {len(paths)}\n')
                f.write('=' * 60 + '\n\n')
                
                for i, path in enumerate(paths, 1):
                    print(f'\nCaminho {i} (comprimento: {len(path)}):')
                    f.write(f'Caminho {i} (comprimento: {len(path)}):\n')
                    
                    # Formatar caminho com labels
                    formatted_path = format_path_with_labels(path, graph)
                    print(formatted_path)
                    f.write(formatted_path + '\n')
                    f.write('-' * 40 + '\n\n')
            
            print(f'\nCaminhos salvos em: {path_output_file}')
        
        # Não continuar com o processamento normal de closure
        return
    
    if closure_target:
        if closure_target not in graph and closure_target not in {n for adj in graph.values() for n in adj}:
            print(f"\nAviso: '{closure_target}' não aparece como nó no grafo. Verifique o caminho relativo.")
        else:
            # Se --direct-deps-only, pegar apenas dependências diretas
            if args.direct_deps_only:
                closure = list(graph.get(closure_target, {}).keys())
                print(f'\nDependências diretas de {closure_target}:')
            else:
                # Para modo shallow (padrão), precisamos passar informações adicionais
                if use_shallow:
                    # Reconstruir as informações necessárias
                    symbols_declared, symbol_to_file = collect_declarations(root, ignore_paths)
                    _, uses = collect_imports_and_usages(root, symbol_to_file, ignore_paths)
                    closure = transitive_closure(
                        graph, closure_target, 
                        include_modules=args.include_modules,
                        shallow_mode=True,
                        symbols_declared=symbols_declared,
                        symbol_to_file=symbol_to_file,
                        uses=uses
                    )
                else:
                    closure = transitive_closure(graph, closure_target, include_modules=args.include_modules)
                print(f'\nFecho transitivo de {closure_target} ({"com" if args.include_modules else "sem"} módulos):')
            
            # Filtrar arquivos ignorados para exibição
            display_closure = []
            for n in closure:
                if not should_ignore_path(n, ignore_paths):
                    display_closure.append(n)
            
            if ignore_paths:
                print(f'(Ignorando: {", ".join(ignore_paths)})')
            if use_shallow:
                print('(Modo shallow: apenas símbolos diretamente usados)')
            else:
                print('(Modo extended: incluindo todos imports e símbolos)')
            
            for n in display_closure:
                # Mostrar labels se for dependência direta
                if args.direct_deps_only and closure_target in graph:
                    labels = graph[closure_target].get(n, [])
                    if labels:
                        print(f'  - {n} [{", ".join(labels)}]')
                    else:
                        print(f'  - {n}')
                else:
                    print(f'  - {n}')
            
            # Filtrar arquivos ignorados do fecho transitivo
            filtered_closure = []
            for n in closure:
                # Pular módulos se não incluir módulos
                if not args.include_modules and (n.startswith('module:') or n.startswith('@module:')):
                    continue
                # Pular arquivos em paths ignorados
                if not should_ignore_path(n, ignore_paths):
                    filtered_closure.append(n)
            
            # Salvar fecho transitivo em arquivo separado
            closure_file = output_dir / f'closure_{Path(closure_target).stem}.txt'
            with open(closure_file, 'w', encoding='utf-8') as f:
                f.write(f'Fecho transitivo direto de {closure_target}:\n')
                f.write(f'(Arquivos dos quais {closure_target} depende)\n')
                f.write(f'({"Incluindo" if args.include_modules else "Excluindo"} módulos externos)\n')
                if ignore_paths:
                    f.write(f'(Ignorando: {", ".join(ignore_paths)})\n')
                f.write('\n')
                for n in filtered_closure:
                    f.write(f'{n}\n')
            print(f'\nFecho transitivo direto salvo em: {closure_file}')
            
            # Gerar arquivo com código dos arquivos se --writeCode foi especificado
            if args.writeCode:
                print('\nGerando arquivo com código dos arquivos do fecho transitivo...')
                
                # Adicionar o arquivo inicial à lista
                all_files = [closure_target] + closure
                
                # Filtrar apenas arquivos locais (não módulos) e não ignorados
                local_files = []
                for f in all_files:
                    # Pular módulos
                    if f.startswith('module:') or f.startswith('@module:'):
                        continue
                    # Pular arquivos em paths ignorados
                    if should_ignore_path(f, ignore_paths):
                        continue
                    local_files.append(f)
                
                # Criar arquivo temporário com a lista de arquivos
                temp_list_file = output_dir / 'temp_files_list.txt'
                with open(temp_list_file, 'w', encoding='utf-8') as f:
                    for file in local_files:
                        f.write(f'{file}\n')
                
                # Executar scan_project.sh
                files_code_path = output_dir / 'files_code.txt'
                script_path = Path(__file__).parent / 'scan_project.sh'
                
                try:
                    result = subprocess.run(
                        ['bash', str(script_path), str(root), str(files_code_path), str(temp_list_file), str(root)],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    print(f'Arquivo com código gerado em: {files_code_path}')
                    
                    # Remover arquivo temporário
                    temp_list_file.unlink()
                    
                except subprocess.CalledProcessError as e:
                    print(f'Erro ao executar scan_project.sh: {e}')
                    print(f'Stderr: {e.stderr}')
                    # Tentar remover arquivo temporário mesmo em caso de erro
                    if temp_list_file.exists():
                        temp_list_file.unlink()
    
    # Detectar ciclos se solicitado
    if args.detect_cycles:
        print('\n🔍 Detectando dependências circulares...')
        cycles = detect_cycles(graph)
        if cycles:
            print(f'\n⚠️  Encontrados {len(cycles)} ciclos:')
            for i, cycle in enumerate(cycles, 1):
                print(f'\nCiclo {i}:')
                for j, node in enumerate(cycle):
                    if j == len(cycle) - 1:
                        print(f'  └─> {node} (volta ao início)')
                    else:
                        print(f'  ├─> {node}')
            
            # Salvar ciclos em arquivo
            cycles_file = output_dir / 'cycles.txt'
            with open(cycles_file, 'w', encoding='utf-8') as f:
                f.write(f'Dependências circulares detectadas: {len(cycles)}\n\n')
                for i, cycle in enumerate(cycles, 1):
                    f.write(f'Ciclo {i}:\n')
                    for node in cycle:
                        f.write(f'  -> {node}\n')
                    f.write('\n')
            print(f'\nCiclos salvos em: {cycles_file}')
        else:
            print('✅ Nenhuma dependência circular detectada!')
    
    # Encontrar órfãos se solicitado
    if args.find_orphans:
        print('\n🔍 Procurando arquivos órfãos...')
        orphans = find_orphan_files(graph, root, ignore_paths)
        if orphans:
            print(f'\n📦 Encontrados {len(orphans)} arquivos órfãos (não referenciados):')
            for orphan in orphans[:20]:  # Mostrar apenas os primeiros 20
                print(f'  - {orphan}')
            if len(orphans) > 20:
                print(f'  ... e mais {len(orphans) - 20} arquivos')
            
            # Salvar órfãos em arquivo
            orphans_file = output_dir / 'orphans.txt'
            with open(orphans_file, 'w', encoding='utf-8') as f:
                f.write(f'Arquivos órfãos (não referenciados): {len(orphans)}\n\n')
                for orphan in orphans:
                    f.write(f'{orphan}\n')
            print(f'\nLista completa salva em: {orphans_file}')
        else:
            print('✅ Nenhum arquivo órfão encontrado!')

if __name__ == '__main__':
    main()