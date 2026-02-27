# core/database.py
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "launcher.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def init_db():
    """Crea la tabla juegos si no existe."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS juegos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            ruta TEXT UNIQUE NOT NULL,
            folder TEXT,
            is_shortcut INTEGER DEFAULT 0,
            resolved_path TEXT,
            playtime INTEGER DEFAULT 0,
            last_played TEXT,
            cover_path TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_all_games():
    """Devuelve lista de diccionarios con todos los juegos ordenados por nombre."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT nombre, ruta, folder, is_shortcut, resolved_path, playtime, last_played, cover_path
        FROM juegos
        ORDER BY nombre COLLATE NOCASE
    ''')
    rows = c.fetchall()
    conn.close()
    juegos = []
    for row in rows:
        juegos.append({
            "nombre": row[0],
            "ruta": row[1],
            "folder": row[2],
            "is_shortcut": bool(row[3]),
            "resolved_path": row[4],
            "playtime": row[5] if row[5] is not None else 0,
            "last_played": row[6],
            "cover_path": row[7]
        })
    return juegos

def insert_or_update_game(game_dict):
    """
    Inserta o actualiza un juego en la BD.
    game_dict debe contener al menos: nombre, ruta, folder, is_shortcut, resolved_path.
    Opcionalmente puede incluir playtime, last_played, cover_path.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Asegurar valores por defecto
    nombre = game_dict.get("nombre", "")
    ruta = game_dict.get("ruta", "")
    folder = game_dict.get("folder", "")
    is_shortcut = 1 if game_dict.get("is_shortcut") else 0
    resolved_path = game_dict.get("resolved_path")
    playtime = game_dict.get("playtime", 0)
    last_played = game_dict.get("last_played")
    cover_path = game_dict.get("cover_path")

    c.execute('''
        INSERT INTO juegos (nombre, ruta, folder, is_shortcut, resolved_path, playtime, last_played, cover_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ruta) DO UPDATE SET
            nombre=excluded.nombre,
            folder=excluded.folder,
            is_shortcut=excluded.is_shortcut,
            resolved_path=excluded.resolved_path,
            playtime=excluded.playtime,
            last_played=excluded.last_played,
            cover_path=excluded.cover_path
    ''', (nombre, ruta, folder, is_shortcut, resolved_path, playtime, last_played, cover_path))
    conn.commit()
    conn.close()

def update_playtime(ruta, minutes, last_played=None):
    """Incrementa los minutos jugados y actualiza última vez."""
    if last_played is None:
        last_played = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        UPDATE juegos
        SET playtime = playtime + ?, last_played = ?
        WHERE ruta = ?
    ''', (minutes, last_played, ruta))
    conn.commit()
    conn.close()

def update_cover_path(ruta, cover_path):
    """Actualiza la ruta de la portada para un juego."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE juegos SET cover_path = ? WHERE ruta = ?', (cover_path, ruta))
    conn.commit()
    conn.close()