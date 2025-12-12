import threading
import mysql.connector

# 数据库连接(mysql.connection)
db_connection = []

lock = threading.Lock()

def create_db_connection():
    conn = mysql.connector.connect(
        host="47.120.51.172",  ### 部署到mysql所在服务器后，注意修改为localhost。
        user="user0",
        password="Taxue_#601",
        database="ordersys_db"
    )
    conn.is_connected()
    return conn

def get_db_connection():
    tid = threading.get_ident()

    for pair in db_connection:
        if pair[0] == tid:
            if not pair[1].is_connected():
                pair[1] = create_db_connection()
            return pair[1]

    lock.acquire_lock()

    conn = create_db_connection()
    if not conn:
        lock.release_lock()
        return None
    db_connection.append((tid,conn))

    lock.release_lock()

    return conn

def get_cursor(dictionary=False):
    conn = get_db_connection()
    return conn.cursor(dictionary=dictionary)