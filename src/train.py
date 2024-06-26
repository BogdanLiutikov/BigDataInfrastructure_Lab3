from configparser import ConfigParser
from pathlib import Path

import pandas as pd
from pickle import dump
from sklearn.base import BaseEstimator
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, classification_report


from .logger import Logger
SHOW_LOG = True
class Trainer:

    def __init__(self, config: ConfigParser, model: BaseEstimator) -> None:
        logger = Logger(SHOW_LOG)
        self.log = logger.get_logger(__name__)
        self.config = config
        self.model = model
        self.fitted = False

    def train(self, X_train: pd.DataFrame, y_train: pd.DataFrame, save_path: str | None = None) -> BaseEstimator:
        self.log.info('Training...')
        self.model = self.model.fit(X_train, y_train)
        self.fitted = True

        print('Training finished')
        if save_path:
            self.save_model(self.model, save_path)
        return self.model

    def save_model(self, save_path: Path):
        self.log.info('Saving model...')
        with open(save_path, 'wb') as file:
            dump(self.model, file)
        model_name = save_path.stem
        if not self.config.has_section('models.fitted'):
                self.config.add_section('models.fitted')
        self.config.set('models.fitted', model_name, save_path.as_posix())
        with open('config.ini', 'w') as configfile:
            self.config.write(configfile)
        return True

    def eval(self):
        data_split = self.config['data.splited']
        x_test_path = data_split['x_test']
        y_test_path = data_split['y_test']

        x_test = pd.read_csv(x_test_path)
        y_test = pd.read_csv(y_test_path).iloc[:, 0]

        predicts = self.model.predict(x_test)
        self.log.info(confusion_matrix(y_test, predicts))
        self.log.info(classification_report(y_test, predicts))
        return True


if __name__ == '__main__':
    config = ConfigParser()
    config.read('config.ini')

    model = RandomForestClassifier()
    trainer = Trainer(config, model)

    x_train = pd.read_csv(config.get('data.splited', 'x_train'))
    y_train = pd.read_csv(config.get('data.splited', 'y_train')).iloc[:, 0]

    model = trainer.train(x_train, y_train)
    save_path = Path(config.get('models', 'save_dir')).joinpath(
        "RandomForestClassifier.pkl")
    trainer.save_model(save_path)
    trainer.log.info('Model evaluate')
    trainer.eval()
