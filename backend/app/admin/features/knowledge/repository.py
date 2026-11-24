from app.admin.core import db


def diseases():
    return db.query('''SELECT disease_id id, disease_name, crop_type, scientific_name, description, active
                       FROM diseases ORDER BY disease_id''')


def disease_exists(disease_id):
    return db.one('SELECT 1 x FROM diseases WHERE disease_id=%s', (disease_id,)) is not None


def add_disease(v):
    return db.execute('INSERT INTO diseases(disease_name,crop_type,scientific_name,description,active) '
                      'VALUES (%s,%s,%s,%s,%s)', v)[0]


def update_disease(disease_id, v):
    db.execute('''UPDATE diseases SET disease_name=%s,crop_type=%s,scientific_name=%s,description=%s,active=%s
                  WHERE disease_id=%s''', (*v, disease_id))


def delete_disease(disease_id):
    return db.execute('DELETE FROM diseases WHERE disease_id=%s', (disease_id,))[1]


def recommendations():
    return db.query('''SELECT r.recommendation_id id, r.disease_id, d.disease_name, r.title, r.recommendation_text,
                       r.precautions, r.source_reference, r.active FROM treatment_recommendations r
                       JOIN diseases d ON d.disease_id=r.disease_id ORDER BY r.recommendation_id''')


def recommendation_exists(rec_id):
    return db.one('SELECT 1 x FROM treatment_recommendations WHERE recommendation_id=%s', (rec_id,)) is not None


def add_recommendation(v):
    return db.execute('''INSERT INTO treatment_recommendations(disease_id,title,recommendation_text,precautions,
                         source_reference,active) VALUES (%s,%s,%s,%s,%s,%s)''', v)[0]


def update_recommendation(rec_id, v):
    db.execute('''UPDATE treatment_recommendations SET disease_id=%s,title=%s,recommendation_text=%s,precautions=%s,
                  source_reference=%s,active=%s WHERE recommendation_id=%s''', (*v, rec_id))


def delete_recommendation(rec_id):
    return db.execute('DELETE FROM treatment_recommendations WHERE recommendation_id=%s', (rec_id,))[1]
