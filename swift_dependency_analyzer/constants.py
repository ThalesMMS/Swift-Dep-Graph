"""
Constantes e configurações globais do Swift Dependency Analyzer.
"""

# Extensões de arquivo suportadas
OBJC_EXTS = {'.m', '.mm', '.h', '.hh'}
SWIFT_EXTS = {'.swift'}
SUPPORTED_EXTS = OBJC_EXTS | SWIFT_EXTS

# Palavras-chave comuns que devem ser ignoradas na análise
COMMON_KEYWORDS = {
    # Palavras-chave básicas
    'self', 'super', 'nil', 'null', 'true', 'false', 'YES', 'NO',
    
    # Métodos de ciclo de vida
    'init', 'dealloc', 'alloc', 'new', 'copy', 'retain', 'release', 'autorelease',
    'description', 'debugDescription', 'hash', 'isEqual', 'class',
    
    # Métodos de controle
    'cancel', 'start', 'stop', 'pause', 'resume', 'reset', 'clear', 'refresh',
    
    # Métodos de I/O
    'load', 'save', 'open', 'close', 'read', 'write', 'delete', 'remove',
    
    # Métodos de coleção
    'add', 'insert', 'update', 'replace', 'get', 'set', 'count', 'size',
    'begin', 'end', 'first', 'last', 'next', 'previous', 'current',
    
    # Métodos de UI
    'show', 'hide', 'enable', 'disable', 'validate', 'invalidate',
    
    # Métodos de rede
    'connect', 'disconnect', 'send', 'receive', 'process', 'handle',
    
    # Métodos de logging
    'error', 'warning', 'info', 'debug', 'log', 'print', 'format',
    
    # Métodos de serialização
    'encode', 'decode', 'serialize', 'deserialize', 'parse', 'stringify',
    
    # Métodos adicionais
    'startListening', 'stopListening', 'isListening'
}

# Tipos básicos do Swift que devem ser ignorados
SWIFT_BASIC_TYPES = {
    'String', 'Int', 'Bool', 'Double', 'Float', 'Any', 'AnyObject', 
    'Void', 'NSObject', 'Array', 'Dictionary', 'Set', 'Optional'
}

# Protocolos comuns do Swift que devem ser ignorados
SWIFT_COMMON_PROTOCOLS = {
    'Codable', 'Equatable', 'Hashable', 'Comparable', 'Decodable', 'Encodable'
}