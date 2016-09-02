
import os
import csv
import sqlite3
import sqlite_funcs

def make_db(data_file, var_file, db_file):
    create_variables_table(var_file, db_file)
    create_data_table(data_file, db_file)

def create_variables_table(var_file, db_file):
    print("Create variables table...")
    con = sqlite3.connect(db_file)
    with con:
        cur = con.cursor()
        cur.execute("DROP TABLE IF EXISTS variables;")
        cur.execute("""CREATE TABLE variables(id INTEGER,
                                                    Name TEXT,
                                                    Unit TEXT,
                                                    Format TEXT,
                                                    HighLimit REAL,
                                                    LowLimit REAL);""")
        with open(var_file, 'rbU') as fin:  # `with` statement available in 2.5+
            # csv.DictReader uses first line in file for column headings by default
            dr = csv.DictReader(fin)  # comma is default delimiter
            to_db = [(i['id'], i['Name'], i['Unit'], i['Format'], i['HighLimit'], i['LowLimit']) for i in dr]
            cur.executemany(
                "INSERT INTO variables (id, Name, Unit, Format, HighLimit, LowLimit) VALUES (?, ?, ?, ?, ?, ?);", to_db)
            con.commit()

def create_data_table(data_file, db_file):
    print("Create wbe_data table...")
    con = sqlite3.connect(db_file)
    with con:
        cur = con.cursor()
        cur.execute("DROP TABLE IF EXISTS data;")
        cur.execute("""CREATE TABLE raw_data(ObjectId INTEGER,
                                                VariableId INTEGER,
                                                PostTime DATETIME,
                                                dependent_val REAL,
                                                independent_val1 REAL,
                                                independent_val2 REAL,
                                                independent_val3 REAL,
                                                independent_val4 REAL,
                                                independent_val5 REAL);""")
        with open(data_file, 'rbU') as fin:  # `with` statement available in 2.5+
            # csv.DictReader uses first line in file for column headings by default
            dr = csv.DictReader(fin)  # comma is default delimiter
            # to_db = [(i['ObjectId'], i['VariableId'], i['PostTime'], i['Value'], i['Value1']) for i in dr]
            to_db = [(1, 3, i['posttime'], i['wbe [kW]'], i['Tout [F]']) for i in dr]
            cur.executemany("INSERT INTO raw_data (ObjectId, VariableId, PostTime, dependent_val, independent_val1) "
                            "VALUES (?, ?, ?, ?, ?);", to_db)
            con.commit()
            # cur.execute("SELECT * FROM wbe_data Limit 3")
            # print(self.pretty_print(cur,None,0))

        print("Create wbe_data aggregation table...")
        cur.execute("""CREATE TABLE wbe_data(ObjectId INTEGER,
            VariableId INTEGER,
            PostTime DATETIME,
            dependent_val REAL,
            independent_val1 REAL,
            independent_val2 REAL,
            independent_val3 REAL,
            independent_val4 REAL,
            independent_val5 REAL);""")
        cur.execute("""INSERT INTO wbe_data (ObjectId, VariableId, PostTime, dependent_val, independent_val1)
                    SELECT ObjectId, VariableId, PostTime, AVG(dependent_val) AS dependent_val, AVG(independent_val1) AS independent_val1
                    FROM raw_data
                    GROUP BY  ObjectId, VariableId,
                              strftime('%Y', raw_data.PostTime),
                              strftime('%m', raw_data.PostTime),
                              strftime('%d', raw_data.PostTime),
                              strftime('%H', raw_data.PostTime)""")




def create_funcs(con):
    print("Create custom functions...")
    con.create_aggregate("median", 1, sqlite_funcs.Median)
    con.create_aggregate("rmse", 2, sqlite_funcs.Rmse)
    con.create_aggregate("mbe", 2, sqlite_funcs.Mbe)