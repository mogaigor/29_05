from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
import csv
import os
import random
import string
import datetime

app = Flask(__name__)
app.secret_key = 'bancomat_secret_key'

USERS_CSV = 'users.csv'
TRANSAZIONI_CSV = 'transazioni.csv'

def load_cards():
    cards = {}
    if os.path.exists(USERS_CSV):
        with open(USERS_CSV, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                cards[row['card_number']] = {
                    'pin': row['pin'],
                    'balance': float(row['balance']),
                    'iban': row.get('iban', ''),
                    'nome': row.get('nome', ''),
                    'cognome': row.get('cognome', '')
                }
    return cards

def save_cards(cards):
    with open(USERS_CSV, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['card_number', 'pin', 'balance', 'iban', 'nome', 'cognome']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for card_number, data in cards.items():
            writer.writerow({
                'card_number': card_number,
                'pin': data['pin'],
                'balance': data['balance'],
                'iban': data.get('iban', ''),
                'nome': data.get('nome', ''),
                'cognome': data.get('cognome', '')
            })

def generate_iban():
    country = 'IT'
    check_digits = str(random.randint(10, 99))
    letters = ''.join(random.choices(string.ascii_uppercase, k=2))
    numbers = ''.join(random.choices(string.digits, k=22))
    return f"{country}{check_digits}{letters}{numbers}"

CARDS = load_cards()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'card_number' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        card_number = request.form['card_number']
        card = CARDS.get(card_number)
        if card:
            session['card_number'] = card_number
            return redirect(url_for('dashboard'))
        else:
            flash('Numero carta non valido', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        card_number = request.form['card_number']
        pin = request.form['pin']
        nome = request.form['nome']
        cognome = request.form['cognome']
        if not (card_number.isdigit() and len(card_number) == 16):
            flash('Il numero carta deve essere di 16 cifre.', 'danger')
        elif not (pin.isdigit() and len(pin) == 5):
            flash('Il PIN deve essere di 5 cifre.', 'danger')
        elif not nome or not cognome:
            flash('Nome e cognome sono obbligatori.', 'danger')
        elif card_number in CARDS:
            flash('Carta già registrata', 'danger')
        else:
            iban = generate_iban()
            CARDS[card_number] = {'pin': pin, 'balance': 0.0, 'iban': iban, 'nome': nome, 'cognome': cognome}
            save_cards(CARDS)
            flash('Carta registrata con successo! Ora puoi accedere.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    card = CARDS[session['card_number']]
    return render_template('dashboard.html', balance=card['balance'], iban=card.get('iban', ''))

@app.route('/saldo')
@login_required
def saldo():
    card = CARDS[session['card_number']]
    return render_template('saldo.html', balance=card['balance'])

@app.route('/prelievo', methods=['GET', 'POST'])
@login_required
def prelievo():
    card = CARDS[session['card_number']]
    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])
            if amount <= 0:
                flash('Importo non valido', 'danger')
            elif amount > card['balance']:
                flash('Saldo insufficiente', 'danger')
            else:
                card['balance'] -= amount
                save_cards(CARDS)
                save_transazione(session['card_number'], 'Prelievo', amount, 'Prelievo contanti')
                flash(f'Prelievo di {amount:.2f}€ effettuato', 'success')
                return redirect(url_for('dashboard'))
        except ValueError:
            flash('Inserisci un importo valido', 'danger')
    return render_template('prelievo.html', balance=card['balance'])

@app.route('/deposito', methods=['GET', 'POST'])
@login_required
def deposito():
    card = CARDS[session['card_number']]
    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])
            if amount <= 0:
                flash('Importo non valido', 'danger')
            else:
                card['balance'] += amount
                save_cards(CARDS)
                save_transazione(session['card_number'], 'Deposito', amount, 'Deposito contanti')
                flash(f'Deposito di {amount:.2f}€ effettuato', 'success')
                return redirect(url_for('dashboard'))
        except ValueError:
            flash('Inserisci un importo valido', 'danger')
    return render_template('deposito.html', balance=card['balance'])

@app.route('/bonifico', methods=['GET', 'POST'])
@login_required
def bonifico():
    card = CARDS[session['card_number']]
    iban_destinatario = None
    nome_dest = ''
    cognome_dest = ''
    if request.method == 'POST':
        nome_dest = request.form.get('nome_dest', '').strip()
        cognome_dest = request.form.get('cognome_dest', '').strip()
        importo = request.form.get('importo')
        destinatario_card = None
        for cnum, cdata in CARDS.items():
            if cdata.get('nome', '').lower() == nome_dest.lower() and cdata.get('cognome', '').lower() == cognome_dest.lower():
                destinatario_card = cnum
                iban_destinatario = cdata.get('iban', '')
                break
        if 'cerca' in request.form:
            if not destinatario_card:
                flash('Destinatario non trovato.', 'danger')
        elif 'invia' in request.form:
            try:
                importo = float(importo)
                if not destinatario_card:
                    flash('Destinatario non trovato.', 'danger')
                elif destinatario_card == session['card_number']:
                    flash('Non puoi inviare un bonifico a te stesso.', 'danger')
                elif importo <= 0:
                    flash('Importo non valido.', 'danger')
                elif importo > card['balance']:
                    flash('Saldo insufficiente.', 'danger')
                else:
                    card['balance'] -= importo
                    CARDS[destinatario_card]['balance'] += importo
                    save_cards(CARDS)
                    save_transazione(session['card_number'], 'Bonifico inviato', importo, f'A {nome_dest} {cognome_dest}')
                    save_transazione(destinatario_card, 'Bonifico ricevuto', importo, f'Da {card["nome"]} {card["cognome"]}')
                    flash(f'Bonifico di {importo:.2f}€ inviato con successo!', 'success')
                    return redirect(url_for('dashboard'))
            except ValueError:
                flash('Inserisci un importo valido.', 'danger')
    return render_template('bonifico.html', balance=card['balance'], iban_destinatario=iban_destinatario, nome_dest=nome_dest, cognome_dest=cognome_dest)

def load_transazioni(card_number):
    transazioni = []
    if os.path.exists(TRANSAZIONI_CSV):
        with open(TRANSAZIONI_CSV, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['card_number'] == card_number:
                    importo = row['importo']
                    tipo = row['tipo']
                    if tipo in ['Deposito', 'Bonifico ricevuto']:
                        importo = f"+{importo}"
                    else:
                        importo = f"-{importo}"
                    transazioni.append({
                        'data': row['data'],
                        'tipo': tipo,
                        'importo': importo,
                        'causale': row['causale']
                    })
    return transazioni[::-1]  # Mostra le più recenti prima

@app.route('/transazioni')
@login_required
def transazioni():
    card_number = session['card_number']
    transazioni = load_transazioni(card_number)
    return render_template('transazioni.html', transazioni=transazioni)

@app.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('login'))

def save_transazione(card_number, tipo, importo, causale):
    with open(TRANSAZIONI_CSV, 'a', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['card_number', 'data', 'tipo', 'importo', 'causale']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if csvfile.tell() == 0:
            writer.writeheader()
        writer.writerow({
            'card_number': card_number,
            'data': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'tipo': tipo,
            'importo': f'{importo:.2f}',
            'causale': causale
        })

if __name__ == '__main__':
    app.run(debug=True)
