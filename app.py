from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dateutil.relativedelta import relativedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'votre_clé_secrète_ici'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gym.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy()

class OffrePaiement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prix = db.Column(db.Float, nullable=False)
    duree_mois = db.Column(db.Integer, nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

class Renouvellement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    offre_id = db.Column(db.Integer, db.ForeignKey('offre_paiement.id'), nullable=False)
    date_debut = db.Column(db.DateTime, nullable=False)
    date_fin = db.Column(db.DateTime, nullable=False)
    date_renouvellement = db.Column(db.DateTime, default=datetime.utcnow)
    actif = db.Column(db.Boolean, default=True)
    
    # Relations
    client = db.relationship('Client', backref='renouvellements')
    offre = db.relationship('OffrePaiement')

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    cin = db.Column(db.String(20), unique=True, nullable=False)
    telephone = db.Column(db.String(20))
    date_inscription = db.Column(db.DateTime, default=datetime.utcnow)
    abonnement = db.Column(db.String(50))
    date_fin_abonnement = db.Column(db.DateTime)

@app.route('/', methods=['GET'])
def index():
    search_query = request.args.get('search', '').strip()
    
    if search_query:
        # Recherche sur nom, prénom ou CIN
        search = f"%{search_query}%"
        clients = Client.query.filter(
            db.or_(
                Client.nom.ilike(search),
                Client.prenom.ilike(search),
                Client.cin.ilike(search)
            )
        ).all()
    else:
        clients = Client.query.all()
    
    return render_template('index.html', clients=clients, search_query=search_query)

@app.route('/ajouter_client', methods=['GET', 'POST'])
def ajouter_client():
    if request.method == 'POST':
        nom = request.form['nom']
        prenom = request.form['prenom']
        cin = request.form['cin']
        telephone = request.form['telephone']
        offre_id = request.form['abonnement']
        
        offre = OffrePaiement.query.get(offre_id)
        if offre:
            # Calculer la date de fin en fonction de la durée de l'offre
            date_debut = datetime.now()
            date_fin = date_debut + relativedelta(months=+offre.duree_mois)
            
            nouveau_client = Client(
                nom=nom,
                prenom=prenom,
                cin=cin,
                telephone=telephone,
                abonnement=offre.nom,
                date_fin_abonnement=date_fin
            )
            
            try:
                db.session.add(nouveau_client)
                db.session.commit()
                flash('Client ajouté avec succès!', 'success')
                return redirect(url_for('index'))
            except:
                db.session.rollback()
                flash('Erreur lors de l\'ajout du client.', 'error')
        else:
            flash('Offre d\'abonnement invalide.', 'error')
    
    offres = OffrePaiement.query.all()
    return render_template('ajouter_client.html', offres=offres)

@app.route('/modifier_client/<int:id>', methods=['GET', 'POST'])
def modifier_client(id):
    client = Client.query.get_or_404(id)
    if request.method == 'POST':
        client.nom = request.form['nom']
        client.prenom = request.form['prenom']
        client.cin = request.form['cin']
        client.telephone = request.form['telephone']
        offre_id = request.form['abonnement']
        
        offre = OffrePaiement.query.get(offre_id)
        if offre:
            client.abonnement = offre.nom
            # Calculer la nouvelle date de fin en fonction de la durée de l'offre
            date_debut = datetime.now()
            client.date_fin_abonnement = date_debut + relativedelta(months=+offre.duree_mois)
            
            try:
                db.session.commit()
                flash('Client modifié avec succès!', 'success')
                return redirect(url_for('index'))
            except:
                db.session.rollback()
                flash('Erreur lors de la modification du client.', 'error')
        else:
            flash('Offre d\'abonnement invalide.', 'error')
    
    offres = OffrePaiement.query.all()
    return render_template('modifier_client.html', client=client, offres=offres)

@app.route('/renouveler_abonnement/<int:client_id>', methods=['GET', 'POST'])
def renouveler_abonnement(client_id):
    client = Client.query.get_or_404(client_id)
    offres = OffrePaiement.query.all()
    
    if request.method == 'POST':
        offre_id = request.form['offre_id']
        type_renouvellement = request.form['type_renouvellement']
        
        offre = OffrePaiement.query.get(offre_id)
        if offre:
            # Déterminer la date de début en fonction du type de renouvellement
            if type_renouvellement == 'immediate':
                date_debut = datetime.now()
                # Désactiver l'ancien abonnement s'il existe
                ancien_renouvellement = Renouvellement.query.filter_by(client_id=client.id, actif=True).first()
                if ancien_renouvellement:
                    ancien_renouvellement.actif = False
            else:  # 'after_expiration'
                date_debut = client.date_fin_abonnement
            
            # Calculer la nouvelle date de fin
            date_fin = date_debut + relativedelta(months=+offre.duree_mois)
            
            # Créer le nouveau renouvellement
            nouveau_renouvellement = Renouvellement(
                client_id=client.id,
                offre_id=offre.id,
                date_debut=date_debut,
                date_fin=date_fin
            )
            
            try:
                db.session.add(nouveau_renouvellement)
                # Mettre à jour les informations du client
                if type_renouvellement == 'immediate':
                    client.abonnement = offre.nom
                    client.date_fin_abonnement = date_fin
                db.session.commit()
                flash('Abonnement renouvelé avec succès!', 'success')
            except:
                db.session.rollback()
                flash('Erreur lors du renouvellement.', 'error')
            
            return redirect(url_for('index'))
    
    # Récupérer l'historique des renouvellements
    historique = Renouvellement.query.filter_by(client_id=client.id).order_by(Renouvellement.date_renouvellement.desc()).all()
    
    return render_template('renouveler_abonnement.html', 
                           client=client, 
                           offres=offres, 
                           historique=historique)

@app.route('/supprimer_client/<int:id>')
def supprimer_client(id):
    client = Client.query.get_or_404(id)
    try:
        # Supprimer d'abord tous les renouvellements associés
        Renouvellement.query.filter_by(client_id=id).delete()
        db.session.delete(client)
        db.session.commit()
        flash('Client supprimé avec succès!', 'success')
    except:
        db.session.rollback()
        flash('Erreur lors de la suppression du client.', 'error')
    return redirect(url_for('index'))

@app.route('/offres')
def liste_offres():
    offres = OffrePaiement.query.all()
    return render_template('offres.html', offres=offres)

@app.route('/ajouter_offre', methods=['GET', 'POST'])
def ajouter_offre():
    if request.method == 'POST':
        nom = request.form['nom']
        prix = float(request.form['prix'])
        duree_mois = int(request.form['duree_mois'])
        
        nouvelle_offre = OffrePaiement(
            nom=nom,
            prix=prix,
            duree_mois=duree_mois
        )
        
        try:
            db.session.add(nouvelle_offre)
            db.session.commit()
            flash('Offre ajoutée avec succès!', 'success')
            return redirect(url_for('liste_offres'))
        except:
            db.session.rollback()
            flash('Erreur lors de l\'ajout de l\'offre.', 'error')
    
    return render_template('ajouter_offre.html')

@app.route('/modifier_offre/<int:id>', methods=['GET', 'POST'])
def modifier_offre(id):
    offre = OffrePaiement.query.get_or_404(id)
    if request.method == 'POST':
        offre.nom = request.form['nom']
        offre.prix = float(request.form['prix'])
        offre.duree_mois = int(request.form['duree_mois'])
        
        try:
            db.session.commit()
            flash('Offre modifiée avec succès!', 'success')
            return redirect(url_for('liste_offres'))
        except:
            db.session.rollback()
            flash('Erreur lors de la modification de l\'offre.', 'error')
    
    return render_template('modifier_offre.html', offre=offre)

@app.route('/supprimer_offre/<int:id>')
def supprimer_offre(id):
    offre = OffrePaiement.query.get_or_404(id)
    try:
        db.session.delete(offre)
        db.session.commit()
        flash('Offre supprimée avec succès!', 'success')
    except:
        db.session.rollback()
        flash('Erreur lors de la suppression de l\'offre.', 'error')
    return redirect(url_for('liste_offres'))

def init_app():
    db.init_app(app)
    with app.app_context():
        db.create_all()
    return app

if __name__ == '__main__':
    init_app()
    app.run(debug=True)
