from flask import Flask, render_template, request, redirect, url_for, session, flash
import webbrowser
import threading

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Cambia in produzione

# La classe Bancomat
class Bancomat:
    def __init__(self, saldo_iniziale, limite_prelievo_giornaliero):
        self.saldo = saldo_iniziale
        self.limite_prelievo_giornaliero = limite_prelievo_giornaliero
        self.transazioni = []
        self.utenti = {}
        self.prelievo_giornaliero = {}  # Cambiato: ora è un dizionario per utente

    def aggiungi_utente(self, username, pin):
        if username in self.utenti:
            return False
        self.utenti[username] = {"pin": pin, "saldo": self.saldo}
        self.prelievo_giornaliero[username] = 0  # Inizializza il prelievo giornaliero per l'utente
        return True

    def autentica(self, username, pin):
        return username in self.utenti and self.utenti[username]["pin"] == pin

    def mostra_saldo(self, username):
        if username not in self.utenti:
            return 0.0
        return self.utenti[username]["saldo"]

    def prelievo(self, username, importo):
        if username not in self.utenti:
            return "Utente non trovato!"
        if importo > self.utenti[username]["saldo"]:
            return "Saldo insufficiente!"
        if self.prelievo_giornaliero.get(username, 0) + importo > self.limite_prelievo_giornaliero:
            return f"Limite giornaliero di prelievo superato! Il massimo che puoi prelevare oggi è {self.limite_prelievo_giornaliero - self.prelievo_giornaliero.get(username, 0)}€."
        self.utenti[username]["saldo"] -= importo
        self.prelievo_giornaliero[username] = self.prelievo_giornaliero.get(username, 0) + importo
        self.transazioni.append(f"Prelievo di {importo}€ effettuato da {username}.")
        return f"Hai prelevato {importo}€. Il tuo saldo attuale è: {self.utenti[username]['saldo']}€"

    def deposito(self, username, importo):
        if username not in self.utenti:
            return "Utente non trovato!"
        self.utenti[username]["saldo"] += importo
        self.transazioni.append(f"Deposito di {importo}€ effettuato da {username}.")
        return f"Hai depositato {importo}€. Il tuo saldo attuale è: {self.utenti[username]['saldo']}€"

    def mostra_cronologia(self):
        return self.transazioni

    def bonifico(self, username_sorgente, username_destinatario, importo):
        if username_sorgente not in self.utenti:
            return "L'utente sorgente non esiste."
        if username_destinatario not in self.utenti:
            return "Il destinatario non esiste."
        if self.utenti[username_sorgente]["saldo"] < importo:
            return "Saldo insufficiente per il bonifico!"
        self.utenti[username_sorgente]["saldo"] -= importo
        self.utenti[username_destinatario]["saldo"] += importo
        self.transazioni.append(f"Bonifico di {importo}€ da {username_sorgente} a {username_destinatario}.")
        return f"Bonifico effettuato con successo! Hai trasferito {importo}€ a {username_destinatario}."


bancomat = Bancomat(1000.0, 500.0)
bancomat.aggiungi_utente("Mario", "1234")
bancomat.aggiungi_utente("Luigi", "5678")

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('home'))
    return render_template('index.html')

@app.route('/registrati')
def registrati():
    if 'username' in session:
        return redirect(url_for('home'))
    return render_template('registrati.html')

@app.route('/registrazione', methods=['POST'])
def registrazione():
    username = request.form.get('username')
    pin = request.form.get('pin')
    if not username or not pin:
        flash("Username e PIN sono obbligatori.", "error")
        return redirect(url_for('registrati'))
    if bancomat.aggiungi_utente(username, pin):
        flash(f"Registrazione completata con successo! Puoi ora accedere.", "success")
        return redirect(url_for('index'))
    else:
        flash(f"L'utente {username} esiste già. Scegli un altro nome utente.", "error")
        return redirect(url_for('registrati'))

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    pin = request.form.get('pin')
    if not username or not pin:
        flash("Username e PIN sono obbligatori.", "error")
        return redirect(url_for('index'))
    if bancomat.autentica(username, pin):
        session['username'] = username
        return redirect(url_for('home'))
    else:
        flash("Credenziali errate. Riprova.", "error")
        return redirect(url_for('index'))

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('index'))
    username = session['username']
    saldo = bancomat.mostra_saldo(username)
    transazioni = bancomat.mostra_cronologia()  # Mostra la cronologia delle transazioni
    return render_template('home.html', saldo=saldo, transazioni=transazioni)

@app.route('/prelievo', methods=['POST'])
def prelievo():
    if 'username' not in session:
        return redirect(url_for('index'))
    username = session.get('username')
    try:
        importo = float(request.form.get('importo', 0))
        if importo <= 0:
            raise ValueError("L'importo deve essere maggiore di 0.")
    except (ValueError, TypeError):
        flash("Importo non valido. Inserisci un numero maggiore di 0.", "error")
        return redirect(url_for('home'))
    risultato = bancomat.prelievo(username, importo)
    flash(risultato, "info")
    return redirect(url_for('home'))

@app.route('/deposito', methods=['POST'])
def deposito():
    if 'username' not in session:
        return redirect(url_for('index'))
    username = session.get('username')
    try:
        importo = float(request.form.get('importo', 0))
        if importo <= 0:
            raise ValueError("L'importo deve essere maggiore di 0.")
    except (ValueError, TypeError):
        flash("Importo non valido. Inserisci un numero maggiore di 0.", "error")
        return redirect(url_for('home'))
    risultato = bancomat.deposito(username, importo)
    flash(risultato, "info")
    return redirect(url_for('home'))

@app.route('/bonifico', methods=['POST'])
def bonifico():
    if 'username' not in session:
        return redirect(url_for('index'))
    username_sorgente = session.get('username')
    destinatario = request.form.get('destinatario')
    try:
        importo = float(request.form.get('importo', 0))
        if importo <= 0:
            raise ValueError("L'importo deve essere maggiore di 0.")
    except (ValueError, TypeError):
        flash("Importo non valido. Inserisci un numero maggiore di 0.", "error")
        return redirect(url_for('home'))
    risultato = bancomat.bonifico(username_sorgente, destinatario, importo)
    flash(risultato, "info")
    return redirect(url_for('home'))

@app.route('/cronologia')
def cronologia():
    if 'username' not in session:
        return redirect(url_for('index'))
    transazioni = bancomat.mostra_cronologia()
    return render_template('cronologia.html', transazioni=transazioni)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

def open_browser():
    webbrowser.open_new('http://127.0.0.1:5000/')

if __name__ == '__main__':
    threading.Timer(1.25, open_browser).start()
    app.run(debug=True)
