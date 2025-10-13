#!/bin/bash

# --- Configuração ---
# Verificar se os parâmetros obrigatórios foram fornecidos
if [ "$#" -lt 2 ]; then
  echo "Erro: Parâmetros insuficientes."
  echo "Uso: $0 <diretório_alvo> <arquivo_saída> [arquivo_lista] [raiz_projeto]"
  echo ""
  echo "Parâmetros:"
  echo "  diretório_alvo - Diretório a ser varrido (obrigatório)"
  echo "  arquivo_saída  - Arquivo onde o código será salvo (obrigatório)"
  echo "  arquivo_lista  - Arquivo com lista de arquivos específicos (opcional)"
  echo "  raiz_projeto   - Diretório raiz para resolver caminhos relativos (opcional)"
  exit 1
fi

TARGET_DIR="$1"
OUTPUT_FILE="$2"

# Terceiro parâmetro opcional: arquivo com lista de arquivos para processar
FILES_LIST=""
if [ "$#" -ge 3 ]; then
  FILES_LIST="$3"
fi

# Quarto parâmetro opcional: diretório raiz do projeto (para caminhos relativos)
PROJECT_ROOT=""
if [ "$#" -ge 4 ]; then
  PROJECT_ROOT="$4"
fi
# --------------------

# Se FILES_LIST foi fornecido, verifica se existe
if [ -n "$FILES_LIST" ] && [ ! -f "$FILES_LIST" ]; then
  echo "Erro: O arquivo com lista de arquivos não foi encontrado em: $FILES_LIST"
  exit 1
fi

# Se FILES_LIST não foi fornecido, verifica se o diretório de destino existe
if [ -z "$FILES_LIST" ] && [ ! -d "$TARGET_DIR" ]; then
  echo "Erro: O diretório de destino não foi encontrado em: $TARGET_DIR"
  exit 1
fi

# Limpa ou cria o arquivo de saída
> "$OUTPUT_FILE"

if [ -n "$FILES_LIST" ]; then
  echo "Processando arquivos listados em: $FILES_LIST"
  echo "O resultado será salvo em: $(pwd)/$OUTPUT_FILE"
  
  # --- Imprime a lista de arquivos ---
  echo "================ LISTA DE ARQUIVOS ================" >> "$OUTPUT_FILE"
  cat "$FILES_LIST" >> "$OUTPUT_FILE"
  echo -e "\n\n" >> "$OUTPUT_FILE"
  # ---------------------------------------------------------
  
  # Processa cada arquivo da lista
  while IFS= read -r filepath; do
    # Pula linhas vazias e comentários
    if [ -z "$filepath" ] || [[ "$filepath" == \#* ]]; then
      continue
    fi
    
    # Constrói o caminho completo do arquivo
    if [ -n "$PROJECT_ROOT" ]; then
      FULL_PATH="$PROJECT_ROOT/$filepath"
    else
      FULL_PATH="$filepath"
    fi
    
    # Verifica se o arquivo existe
    if [ -f "$FULL_PATH" ]; then
      echo "===== $filepath =====" >> "$OUTPUT_FILE"
      cat "$FULL_PATH" >> "$OUTPUT_FILE"
      echo -e "\n" >> "$OUTPUT_FILE"
    else
      echo "Aviso: Arquivo não encontrado: $FULL_PATH" >&2
    fi
  done < "$FILES_LIST"
  
else
  echo "Iniciando a varredura do projeto em: $TARGET_DIR"
  echo "O resultado será salvo em: $(pwd)/$OUTPUT_FILE"
  
  # --- Imprime a estrutura de diretórios ---
  echo "================ ESTRUTURA DE DIRETÓRIOS ================" >> "$OUTPUT_FILE"
  if command -v tree >/dev/null 2>&1; then
      tree "$TARGET_DIR" >> "$OUTPUT_FILE"
  else
      # Se não houver tree instalado, usa find como alternativa
      find "$TARGET_DIR" -print | sed "s|$TARGET_DIR|.|" >> "$OUTPUT_FILE"
  fi
  echo -e "\n\n" >> "$OUTPUT_FILE"
  # ---------------------------------------------------------
  
  # Itera sobre os arquivos de código
  find "$TARGET_DIR" -type f \( -name "*.h" -o -name "*.m" -o -name "*.mm" -o -name "*.swift" -o -name "*.c" \) -print0 \
    | sort -z \
    | while IFS= read -r -d '' filepath; do
      
      RELATIVE_PATH="./${filepath#$TARGET_DIR/}"
      
      echo "===== $RELATIVE_PATH =====" >> "$OUTPUT_FILE"
      cat "$filepath" >> "$OUTPUT_FILE"
      echo -e "\n" >> "$OUTPUT_FILE"
  done
fi

echo "Concluído! O arquivo '$OUTPUT_FILE' foi criado com sucesso."