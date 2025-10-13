"""
Gerador de projeto de teste complexo para validação.
"""

from pathlib import Path
from typing import Dict, Any
from .templates import TEST_PROJECT_STRUCTURE


class TestProjectGenerator:
    """
    Gera projetos de teste com cenários complexos de dependências.
    """
    
    def __init__(self, root_dir: Path = None):
        """
        Inicializa o gerador.
        
        Args:
            root_dir: Diretório raiz para criar o projeto de teste
        """
        self.root_dir = root_dir or (Path.cwd() / 'test_project')
    
    def generate(self) -> Path:
        """
        Gera o projeto de teste completo.
        
        Returns:
            Caminho do projeto criado
        """
        print('🔨 Criando projeto de teste complexo em test_project/')
        print('  Características do projeto de teste:')
        print('  • Ciclos de dependência (A→B→C→A)')
        print('  • Arquivos órfãos isolados')
        print('  • Múltiplos caminhos entre arquivos')
        print('  • Dependências profundas (5+ níveis)')
        print('  • Integração Swift/Objective-C')
        
        # Criar estrutura de diretórios e arquivos
        self._create_structure(TEST_PROJECT_STRUCTURE)
        
        # Estatísticas
        file_count = self._count_files(TEST_PROJECT_STRUCTURE)
        
        print(f'✅ Projeto de teste complexo criado com sucesso em: {self.root_dir}')
        print(f'   - {file_count} arquivos criados')
        
        self._print_test_scenarios()
        self._print_test_commands()
        
        return self.root_dir
    
    def _create_structure(self, structure: Dict[str, Any]):
        """
        Cria a estrutura de arquivos e diretórios.
        
        Args:
            structure: Dicionário com estrutura do projeto
        """
        for dir_path, files in structure.items():
            if dir_path:
                dir_full_path = self.root_dir / dir_path
            else:
                dir_full_path = self.root_dir
            
            dir_full_path.mkdir(parents=True, exist_ok=True)
            
            for filename, content in files.items():
                file_path = dir_full_path / filename
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding='utf-8')
    
    def _count_files(self, structure: Dict[str, Any]) -> int:
        """
        Conta o número de arquivos na estrutura.
        
        Args:
            structure: Estrutura do projeto
            
        Returns:
            Número de arquivos
        """
        count = 0
        for files in structure.values():
            count += len(files)
        return count
    
    def _print_test_scenarios(self):
        """
        Imprime os cenários de teste incluídos.
        """
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
    
    def _print_test_commands(self):
        """
        Imprime comandos úteis para testar.
        """
        print(f'\n🧪 Comandos úteis para testar:')
        print(f'   python3 swift_dep_analyzer.py test_project --detect-cycles')
        print(f'   python3 swift_dep_analyzer.py test_project --find-orphans')
        print(f'   python3 swift_dep_analyzer.py test_project/MyApp/Controllers/MainViewController.swift')
        print(f'   python3 swift_dep_analyzer.py test_project/MyApp/DeepDependency/Level1.swift')
    
    def clean(self) -> bool:
        """
        Remove o projeto de teste.
        
        Returns:
            True se removeu com sucesso
        """
        if self.root_dir.exists():
            import shutil
            try:
                shutil.rmtree(self.root_dir)
                print(f'🧹 Projeto de teste removido: {self.root_dir}')
                return True
            except Exception as e:
                print(f'❌ Erro ao remover projeto de teste: {e}')
                return False
        else:
            print(f'ℹ️  Projeto de teste não existe: {self.root_dir}')
            return True