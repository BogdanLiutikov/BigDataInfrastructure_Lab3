import json
import os

from sqlalchemy import URL, create_engine, text, select
from sqlalchemy.orm import Session, sessionmaker

from . import models, schemas
from .logger import Logger


class Database:
    def __init__(self, user, password) -> None:
        self.logger = Logger(True).get_logger(__name__)
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

    def __create_database_through_master_database(self, user, password, database_name: str = 'Lab2'):
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
        db.commit()
        db.refresh(db_predict)
        return db_predict

    def get_predictions(self, db: Session):
        return db.query(models.Predict).all()
    
    def get_last_prediction(self, db: Session) -> models.Predict:
        stmt = select(models.Predict).order_by(models.Predict.datatime.desc())
        execute = db.scalars(stmt).first()
        return execute
