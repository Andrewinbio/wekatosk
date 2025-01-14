from sklearn.ensemble import AdaBoostClassifier, GradientBoostingClassifier, RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from xgboost import XGBClassifier

# Define base predictors as dictionary
predictors = {'AdaBoost': AdaBoostClassifier(),
              'DT': DecisionTreeClassifier(),
              'GradientBoosting': GradientBoostingClassifier(),
              'KNN': KNeighborsClassifier(),
              'LR': LogisticRegression(),
              'NB': GaussianNB(),
              'MLP': MLPClassifier(),
              'RF': RandomForestClassifier(),
              'SVM': SVC(kernel='linear', probability=True),
              'XGB': XGBClassifier(use_label_encoder=False, eval_metric='error')}
