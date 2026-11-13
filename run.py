import os
import sys
import webbrowser
import threading
import time
from app import create_app

app = create_app()

def abrir_navegador(url):
    time.sleep(1.2)
    webbrowser.open(url)

if __name__ == '__main__':
    HOST = '127.0.0.1'
    PORT = 5000
    URL = f"http://{HOST}:{PORT}"

    print("=" * 65)
    print("   SISTEMA CASA VIDA - GESTÃO DE ASSISTIDOS")
    print(f"   Iniciando servidor local em: {URL}")
    print("   Pressione Ctrl+C na janela para encerrar o sistema.")
    print("=" * 65)

    if os.environ.get("FLASK_ENV") != "development":
        t = threading.Thread(target=abrir_navegador, args=(URL,), daemon=True)
        t.start()

    try:
        from waitress import serve
        print(f"[INFO] Servidor Waitress ativo.")
        serve(app, host=HOST, port=PORT, threads=6)
    except ImportError:
        print("[AVISO] Executando via servidor embutido do Flask...")
        app.run(host=HOST, port=PORT, debug=False)
