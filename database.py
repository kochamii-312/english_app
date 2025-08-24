import sqlite3
import pandas as pd

DB_PATH = 'english_study.db'

def get_db_connection():
    """データベース接続を取得し、テーブルが存在しない場合は作成する"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # フレーズテーブル
    conn.execute('''
        CREATE TABLE IF NOT EXISTS phrases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder TEXT NOT NULL,
            japanese TEXT NOT NULL,
            english TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # フォルダテーブル
    conn.execute('''
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    # 初期データとしてデフォルトフォルダを作成
    try:
        conn.execute("INSERT INTO folders (name) VALUES (?)", ('MYフレーズ',))
        conn.commit()
    except sqlite3.IntegrityError:
        # すでに存在する場合は何もしない
        pass

    conn.close()

def add_folder(folder_name):
    """新しいフォルダを追加する"""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("INSERT INTO folders (name) VALUES (?)", (folder_name,))
        conn.commit()
    except sqlite3.IntegrityError:
        # フォルダ名が重複している場合
        return False
    finally:
        conn.close()
    return True

def get_folders():
    """すべてのフォルダ名を取得する"""
    conn = sqlite3.connect(DB_PATH)
    folders = conn.execute("SELECT name FROM folders ORDER BY name").fetchall()
    conn.close()
    return [folder['name'] for folder in folders]

def add_phrase(folder, japanese, english):
    """新しいフレーズを追加する"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO phrases (folder, japanese, english) VALUES (?, ?, ?)",
        (folder, japanese, english)
    )
    conn.commit()
    conn.close()

def get_phrases_by_folder(folder):
    """指定されたフォルダのフレーズをPandas DataFrameとして取得する"""
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT id, japanese, english FROM phrases WHERE folder = ? ORDER BY created_at"
    df = pd.read_sql_query(query, conn, params=(folder,))
    conn.close()
    return df

def update_phrase(phrase_id, new_japanese, new_english):
    """フレーズを更新する"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE phrases SET japanese = ?, english = ? WHERE id = ?",
        (new_japanese, new_english, phrase_id)
    )
    conn.commit()
    conn.close()

def delete_phrase(phrase_id):
    """フレーズを削除する"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM phrases WHERE id = ?", (phrase_id,))
    conn.commit()
    conn.close()

# アプリ起動時に一度だけ実行
get_db_connection()