import os
import sys
from app import create_app
from app.sockets import socketio
from flask import send_from_directory

# DEV mode: auto-reload quando alterar .py / templates / static
# Desligue setando FLASK_DEBUG=0 no ambiente
DEV = os.environ.get("FLASK_DEBUG", "1") != "0" and not getattr(sys, "frozen", False)

app = create_app()

if DEV:
    # templates Jinja sempre reconsultados a cada request
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    # estáticos (CSS/JS) sem cache no navegador → muda e Ctrl+R já reflete
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

@app.route('/manifest.json')
def manifest():
    return send_from_directory(
        'static',
        'manifest.json',
        mimetype='application/manifest+json'
    )


def _watched_files():
    """
    Lista arquivos extras pro reloader observar (templates + estáticos).
    O Werkzeug já observa .py automaticamente; aqui adicionamos HTML/CSS/JS
    para que mudanças neles também disparem reload do servidor.
    """
    base = os.path.dirname(os.path.abspath(__file__))
    extras = []
    for folder in (
        os.path.join(base, "app", "templates"),
        os.path.join(base, "app", "static"),
    ):
        for root, _, files in os.walk(folder):
            for f in files:
                if f.endswith((".html", ".css", ".js", ".json")):
                    extras.append(os.path.join(root, f))
    return extras


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=5020,
        debug=DEV,
        use_reloader=DEV,
        extra_files=_watched_files() if DEV else None,
    )
