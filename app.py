from flask import Flask, render_template, request, redirect
import pymysql
from pymysql.cursors import DictCursor

app = Flask(__name__)

# Konfigurasi koneksi ke database
db_config = {
    'host': 'shinkansen.proxy.rlwy.net',
    'user': 'root',
    'password': 'BzUobQyvRWDoeVzGQpDIvsRpdkfwqIns',
    'database': 'railway',
    'port': 58092, #kalo masih localhost, gaperlu ini
    'cursorclass': DictCursor,
    'charset': 'utf8mb4',
    'autocommit': True
}

def get_db_connection():
    return pymysql.connect(**db_config)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def show_data():
    keyword = request.args.get('keyword', '').strip()
    conn = get_db_connection()
    cur = conn.cursor()

    if keyword:
        query = """
            SELECT * FROM data_p 
            WHERE nama LIKE %s OR NIK LIKE %s OR kabkota LIKE %s
        """
        like_keyword = f"%{keyword}%"
        cur.execute(query, (like_keyword, like_keyword, like_keyword))
    else:
        cur.execute("SELECT * FROM data_p")

    data = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('data.html', data=data, keyword=keyword, show_reset=bool(keyword))

@app.route('/edit/<nik>', methods=['GET'])
def edit(nik):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM data_p WHERE NIK = %s", (nik,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('index.html', data=result)

@app.route('/submit', methods=['POST'])
def submit():
    data = request.form
    conn = get_db_connection()
    cur = conn.cursor()

    nama_bank = data.get('nama_bank', '')
    cabang = data.get('cabang', '')
    no_rekening = data.get('no_rekening', '')
    nama_pemilik = data.get('nama_pemilik', '')
    no_telp_rumah = data.get('no_telp_rumah', '')
    no_hp_rumah = data.get('no_hp_rumah', '')
    nama_pasangan = data.get('nama_pasangan', '')
    no_ktp_pasangan = data.get('no_ktp_pasangan', '')
    agama_pasangan = data.get('agama_pasangan', '')
    jenis_kelamin = data.get('jenis_kelamin', '')
    status_pasangan = data.get('status_pasangan', '')

    cur.execute("SELECT * FROM data_p WHERE NIK = %s", (data['NIK'],))
    existing = cur.fetchone()

    if existing:
        cur.execute("""
            UPDATE data_p SET 
                NIK=%s, nama=%s, tgl_lahir=%s, status=%s, NPWP=%s, gol_darah=%s, agama=%s,
                jalan=%s, gang=%s, no_rumah=%s, RT=%s, RW=%s, kel_desa=%s, kecamatan=%s, kabkota=%s, kodepos=%s,
                nama_bank=%s, cabang=%s, no_rekening=%s, nama_pemilik=%s, no_telp_rumah=%s, no_hp=%s,
                nama_pasangan=%s, no_ktp_pasangan=%s, agama_pasangan=%s, jenis_kelamin=%s, status_pasangan=%s
            WHERE NIK = %s
        """, (
            data['NIK'], data['nama'], data['tgl_lahir'], data['status'], data['NPWP'], data['gol_darah'], data['agama'],
            data['jalan'], data['gang'], data['no_rumah'], data['RT'], data['RW'], data['kel_desa'],
            data['kecamatan'], data['kabkota'], data['kodepos'], nama_bank, cabang, no_rekening, nama_pemilik,
            no_telp_rumah, no_hp_rumah, nama_pasangan, no_ktp_pasangan, agama_pasangan, jenis_kelamin,
            status_pasangan, data['NIK']
        ))
    else:
        cur.execute("""
            INSERT INTO data_p (
                NIK, nama, tgl_lahir, status, NPWP, gol_darah, agama, jalan, gang, no_rumah,
                RT, RW, kel_desa, kecamatan, kabkota, kodepos, nama_bank, cabang, no_rekening,
                nama_pemilik, no_telp_rumah, no_hp, nama_pasangan, no_ktp_pasangan, agama_pasangan,
                jenis_kelamin, status_pasangan
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data['NIK'], data['nama'], data['tgl_lahir'], data['status'], data['NPWP'],
            data['gol_darah'], data['agama'], data['jalan'], data['gang'], data['no_rumah'],
            data['RT'], data['RW'], data['kel_desa'], data['kecamatan'], data['kabkota'], data['kodepos'],
            nama_bank, cabang, no_rekening, nama_pemilik, no_telp_rumah, no_hp_rumah,
            nama_pasangan, no_ktp_pasangan, agama_pasangan, jenis_kelamin, status_pasangan
        ))

    conn.commit()
    cur.close()
    conn.close()
    return redirect('/data')

@app.route('/delete/<string:nik>', methods=['GET'])
def delete(nik):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM data_p WHERE NIK = %s", (nik,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect('/data')

if __name__ == '__main__':
    app.run(debug=True)
