"""
Templates para o projeto de teste.
"""

# Estrutura completa do projeto de teste
TEST_PROJECT_STRUCTURE = {
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
        userProfileManager.loadProfile()
    }
}

extension DetailViewController: DetailViewModelDelegate {
    func didUpdateData() {
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
        // CICLO: ThemeManager -> PreferencesManager -> NotificationCenter -> ThemeManager
        preferencesManager.updateThemePreference()
    }
}''',
        'PreferencesManager.swift': '''import Foundation

class PreferencesManager {
    static let shared = PreferencesManager()
    private let notificationCenter = AppNotificationCenter.shared
    
    private init() {}
    
    func updateThemePreference() {
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
    // Load user profile
}

@end''',
        'UserProfileManager.swift': '''import Foundation

class UserProfileManager {
    static let shared = UserProfileManager()
    private let analyticsManager = AnalyticsManager.shared
    
    private init() {}
    
    func loadProfile() {
        analyticsManager.trackProfileLoad()
    }
    
    func updateSettings() {
        // Update profile settings
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