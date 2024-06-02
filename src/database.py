import json
import os
from time import sleep

from httpx import request
from sqlalchemy import URL, create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from . import models, schemas
from .logger import Logger


class Database:
    def __init__(self) -> None:
        self.logger = Logger(True).get_logger(__name__)

        cred = None
        user = None
        password = None
        retries = 5
        
        for i in range(retries):
            try:
                cred = request('get', 'http://vault-server:8200/v1/secret/data/db', headers={'X-Vault-Token': os.environ.get('VAULT_TOKEN')})
                if cred.status_code == 200:
                    cred = cred.json()
                    user = cred['data']['data']['MSSQL_USER']
                    password = cred['data']['data']['MSSQL_SA_PASSWORD']
                    break
            except Exception as e:
                self.logger.info(f'Error while getting credentials from Vauls — {e}. Try again')
                sleep(3)
                continue
            else:
                self.logger.info('No credentiasl in Vault. Try again')
                sleep(3)

        if user and password:
            self.logger.info('Got database credentials from Vault')
        else:
            self.logger.error(f'Cannot get credetials from Vault. Look at last request {cred}')
            return

        db_name = self.__create_database_through_master_database(user, password, 'Lab3')
        connection_url = URL.create(
            "mssql+pyodbc",
            username=user,
            password=password,
            host="mssql",
            port=1433,
            database=db_name,
            query={
                "driver": "ODBC Driver 18 for SQL Server",
                "TrustServerCertificate": "yes",
            }
        )
        self.engine = create_engine(connection_url)
        self.SessionLocal = sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=self.engine)
        try:
            with self.engine.connect() as connection:
                self.logger.info("Соединение с базой данных установлено и работает корректно.")
        except Exception as e:
            self.logger.info(f"Ошибка при попытке установить соединение с базой данных: {e}")

        models.Base.metadata.create_all(self.engine)
        self.logger.info("Все таблицы созданы")

    def __create_database_through_master_database(self, user, password, database_name: str = 'Lab'):
        connection_url = URL.create(
            "mssql+pyodbc",
            username=user,
            password=password,
            host="mssql",
            port=1433,
            database="master",
            query={
                "driver": "ODBC Driver 18 for SQL Server",
                "TrustServerCertificate": "yes",
            }
        )
        engine = create_engine(connection_url,
                               execution_options={"isolation_level": "AUTOCOMMIT"})
        with engine.begin() as conn:
            conn.execute(text(f'''IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = '{database_name}')
                                  BEGIN
                                    CREATE DATABASE {database_name};
                                  END;'''))
        engine.dispose(close=True)
        self.logger.info(f"database {database_name} was created")
        return database_name

    def get_session(self):
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def create_record(self, db: Session, record: schemas.PredictedModel | None):
        for i in range(len(record.y_pred)):
            db_predict = models.Predict(x=json.dumps(record.x[i]),
                                        y_true=record.y_true[i],
                                        y_pred=record.y_pred[i])
            db.add(db_predict)
        self.logger.info("records added")
        db.commit()
        db.refresh(db_predict)
        return db_predict

    def get_predictions(self, db: Session):
        return db.query(models.Predict).all()
    
    def get_last_prediction(self, db: Session) -> models.Predict:
        stmt = select(models.Predict).order_by(models.Predict.datatime.desc())
        execute = db.scalars(stmt).first()
        return execute
