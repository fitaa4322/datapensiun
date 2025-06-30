from flask import Flask, render_template, request, redirect, Response, send_file
import pymysql
from pymysql.cursors import DictCursor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import landscape, A4
import json
from markupsafe import Markup
import base64
import io # Diperlukan untuk CSV
import csv # Diperlukan untuk CSV

app = Flask(__name__)

# Konfigurasi koneksi ke databasef
db_config = {
    'user': 'root',
    'password': '',
    'database': 'dbpensiun',
    'cursorclass': DictCursor,
    'autocommit': True
}

# --- BAGIAN BARU: Muat data kota/kabupaten dari file JSON ---
INDONESIAN_CITIES_REGIONS = []
try:
    with open('regencies.json', 'r', encoding='utf-8') as f:
        regencies_data = json.load(f)
        # Ekstrak hanya nama kota/kabupaten dan urutkan
        INDONESIAN_CITIES_REGIONS = sorted([item['regency'] for item in regencies_data])
    print(f"DEBUG: Berhasil memuat {len(INDONESIAN_CITIES_REGIONS)} kota/kabupaten dari regencies.json")
except FileNotFoundError:
    print("ERROR: File regencies.json tidak ditemukan. Pastikan file tersebut ada di direktori yang sama dengan app.py")
    INDONESIAN_CITIES_REGIONS = ["Data Tidak Tersedia"] # Fallback jika file tidak ditemukan
except json.JSONDecodeError:
    print("ERROR: Gagal membaca file regencies.json. Pastikan formatnya benar.")
    INDONESIAN_CITIES_REGIONS = ["Data Rusak"] # Fallback jika format JSON salah
# --- AKHIR BAGIAN BARU ---


def get_db_connection():
    """Membuka koneksi baru ke database."""
    return pymysql.connect(**db_config)

@app.route('/')
def home_redirect():
    """
    Rute utama. Mengalihkan ke halaman dashboard.
    """
    return redirect('/dashboard')

@app.route('/input_data')
def input_data():
    """
    Rute untuk halaman input data anggota baru.
    Menampilkan form kosong atau form dengan data yang sudah ada jika dalam mode edit.
    """
    print("\n--- DEBUG: Entering input_data route (new form) ---")
    return render_template('index.html', children_data=[], kabkota_options=INDONESIAN_CITIES_REGIONS)


@app.route('/data')
def show_data():
    """
    Rute untuk menampilkan semua data anggota P2TEL dalam tabel.
    Mendukung pencarian berdasarkan nama, NIK, atau kota/kabupaten.
    """
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
    # Hapus all_children_data dari sini karena akan ada di halaman terpisah
    return render_template('data.html', data=data, keyword=keyword)

@app.route('/children_data')
def show_children_data():
    """
    Rute baru untuk menampilkan semua data anak dalam tabel terpisah.
    Mendukung pencarian berdasarkan nama anak atau nama orang tua.
    """
    keyword = request.args.get('keyword', '').strip()
    conn = get_db_connection()
    cur = conn.cursor()

    all_children_data = []
    print("\n--- DEBUG: Memuat Semua Data Anak untuk Tampilan children.html ---")
    
    if keyword:
        # Cari anak berdasarkan nama anak atau nama orang tua
        query = """
            SELECT da.nama_anak, da.no_ktp_anak, da.agama_anak, da.jenis_kelamin_anak,
                   dp.nama AS nama_orangtua, dp.NIK AS NIK_orangtua_for_child_table
            FROM data_anak da
            JOIN data_p dp ON da.NIK_orangtua = dp.NIK
            WHERE da.nama_anak LIKE %s OR dp.nama LIKE %s
            ORDER BY dp.nama, da.nama_anak
        """
        like_keyword = f"%{keyword}%"
        cur.execute(query, (like_keyword, like_keyword))
    else:
        # Ambil semua data anak beserta nama orang tuanya
        cur.execute("""
            SELECT da.nama_anak, da.no_ktp_anak, da.agama_anak, da.jenis_kelamin_anak,
                   dp.nama AS nama_orangtua, dp.NIK AS NIK_orangtua_for_child_table
            FROM data_anak da
            JOIN data_p dp ON da.NIK_orangtua = dp.NIK
            ORDER BY dp.nama, da.nama_anak
        """)
    
    all_children_data = cur.fetchall()
    print(f"DEBUG: Semua data anak yang terkumpul untuk ditampilkan di children.html: {len(all_children_data)} baris.")

    cur.close()
    conn.close()
    return render_template('children.html', all_children_data=all_children_data, keyword=keyword)


@app.route('/edit/<nik>', methods=['GET'])
def edit(nik):
    """
    Rute untuk menampilkan form edit data anggota dan anak-anaknya.
    Data anggota dan anak akan diisi otomatis ke dalam form.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    print(f"\n--- DEBUG FLASK: Entering edit route for NIK: {nik} ---")
    # Ambil data anggota
    cur.execute("SELECT * FROM data_p WHERE NIK = %s", (nik,))
    result = cur.fetchone()
    print(f"DEBUG FLASK: Parent data fetched: {result}")

    # Ambil data anak-anak
    cur.execute("SELECT nama_anak, no_ktp_anak, agama_anak, jenis_kelamin_anak FROM data_anak WHERE NIK_orangtua = %s", (nik,))
    children_data = cur.fetchall()
    print(f"DEBUG FLASK: Children data fetched from DB for NIK {nik}: {children_data}")

    # Encode data anak ke Base64 JSON string agar bisa dilewatkan ke JavaScript
    json_string = json.dumps(children_data)
    children_data_base64 = base64.b64encode(json_string.encode('utf-8')).decode('utf-8')
    print(f"DEBUG FLASK: children_data_base64 (for HTML): {children_data_base64}")

    cur.close()
    conn.close()
    return render_template('index.html', data=result, children_data_base64=children_data_base64, kabkota_options=INDONESIAN_CITIES_REGIONS)


@app.route('/submit', methods=['POST'])
def submit():
    """
    Rute untuk memproses pengiriman form (menambah atau memperbarui data anggota dan anak).
    """
    data = request.form
    conn = get_db_connection()
    cur = conn.cursor()

    # Ambil data anggota dari form
    nama_bank = data.get('nama_bank', '')
    cabang = data.get('cabang', '')
    no_rekening = data.get('no_rekening', '')
    nama_pemilik = data.get('nama_pemilik', '')
    no_telp_rumah = data.get('no_telp_rumah', '')
    no_hp_rumah = data.get('no_hp_rumah', '')
    nama_pasangan = data.get('nama_pasangan', '')
    no_ktp_pasangan = data.get('no_ktp_pasangan', '')
    agama_pasangan = data.get('agama_pasangan', '')
    jenis_kelamin = data.get('jenis_kelamin', '') # Jenis kelamin anggota, bukan pasangan
    status_pasangan = data.get('status_pasangan', '')
    
    # Ambil data tambahan baru
    kondisi_rumah = data.get('kondisi_rumah', '')
    tinggal_bersama = data.get('tinggal_bersama', '')

    # Cek apakah NIK sudah ada
    cur.execute("SELECT * FROM data_p WHERE NIK = %s", (data['NIK'],))
    existing = cur.fetchone()

    try:
        if existing:
            # Perbarui data anggota yang sudah ada
            cur.execute("""
                UPDATE data_p SET
                    nama=%s, tgl_lahir=%s, status=%s, NPWP=%s, gol_darah=%s, agama=%s,
                    jalan=%s, gang=%s, no_rumah=%s, RT=%s, RW=%s, kel_desa=%s, kecamatan=%s, kabkota=%s, kodepos=%s,
                    nama_bank=%s, cabang=%s, no_rekening=%s, nama_pemilik=%s, no_telp_rumah=%s, no_hp=%s,
                    nama_pasangan=%s, no_ktp_pasangan=%s, agama_pasangan=%s, jenis_kelamin=%s, status_pasangan=%s,
                    Kondisi_Rumah=%s, Tinggal_bersama=%s
                WHERE NIK = %s
            """, (
                data['nama'], data['tgl_lahir'], data['status'], data['NPWP'], data['gol_darah'], data['agama'],
                data['jalan'], data['gang'], data['no_rumah'], data['RT'], data['RW'], data['kel_desa'],
                data['kecamatan'], data['kabkota'], data['kodepos'], nama_bank, cabang, no_rekening, nama_pemilik,
                no_telp_rumah, no_hp_rumah, nama_pasangan, no_ktp_pasangan, agama_pasangan, jenis_kelamin,
                status_pasangan, kondisi_rumah, tinggal_bersama, data['NIK']
            ))
            print(f"DEBUG: Data anggota berhasil diperbarui untuk NIK: {data['NIK']}")
        else:
            # Tambahkan data anggota baru
            cur.execute("""
                INSERT INTO data_p (
                    NIK, nama, tgl_lahir, status, NPWP, gol_darah, agama, jalan, gang, no_rumah,
                    RT, RW, kel_desa, kecamatan, kabkota, kodepos, nama_bank, cabang, no_rekening,
                    nama_pemilik, no_telp_rumah, no_hp, nama_pasangan, no_ktp_pasangan, agama_pasangan,
                    jenis_kelamin, status_pasangan, Kondisi_Rumah, Tinggal_bersama
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data['NIK'], data['nama'], data['tgl_lahir'], data['status'], data['NPWP'],
                data['gol_darah'], data['agama'], data['jalan'], data['gang'], data['no_rumah'],
                data['RT'], data['RW'], data['kel_desa'], data['kecamatan'], data['kabkota'], data['kodepos'],
                nama_bank, cabang, no_rekening, nama_pemilik, no_telp_rumah, no_hp_rumah,
                nama_pasangan, no_ktp_pasangan, agama_pasangan, jenis_kelamin, status_pasangan,
                kondisi_rumah, tinggal_bersama
            ))
            print(f"DEBUG: Data anggota baru berhasil ditambahkan untuk NIK: {data['NIK']}")

        # Proses data anak
        jumlah_anak_str = data.get('jumlahAnak', '0')
        try:
            jumlah_anak = int(jumlah_anak_str)
        except ValueError:
            jumlah_anak = 0
        print(f"\n--- DEBUG: Memproses Data Anak untuk NIK: {data['NIK']} ---")
        print(f"DEBUG: Jumlah anak yang diidentifikasi dari form: {jumlah_anak}")

        NIK_orangtua = data['NIK']

        # Hapus data anak yang sudah ada untuk NIK ini sebelum memasukkan yang baru
        cur.execute("DELETE FROM data_anak WHERE NIK_orangtua = %s", (NIK_orangtua,))
        print(f"DEBUG: Data anak yang ada dihapus untuk NIK: {NIK_orangtua}")

        # Masukkan data anak baru
        for i in range(1, jumlah_anak + 1):
            nama_anak = data.get(f'nama_anak_{i}')
            no_ktp_anak = data.get(f'no_ktp_anak_{i}')
            agama_anak = data.get(f'agama_anak_{i}')
            jenis_kelamin_anak = data.get(f'jenis_kelamin_anak_{i}')

            if nama_anak and no_ktp_anak and agama_anak and jenis_kelamin_anak:
                cur.execute("""
                    INSERT INTO data_anak (NIK_orangtua, nama_anak, no_ktp_anak, agama_anak, jenis_kelamin_anak)
                    VALUES (%s, %s, %s, %s, %s)
                """, (NIK_orangtua, nama_anak, no_ktp_anak, agama_anak, jenis_kelamin_anak))
                print(f"DEBUG: Berhasil menambahkan data anak ke-{i}: Nama={nama_anak}, KTP={no_ktp_anak}, Agama={agama_anak}, JenisKelamin={jenis_kelamin_anak}")
            else:
                print(f"DEBUG: Melewati data anak ke-{i} karena ada data yang hilang: Nama={nama_anak}, KTP={no_ktp_anak}, Agama={agama_anak}, JenisKelamin={jenis_kelamin_anak}")

        conn.commit()
        print("DEBUG: Data anggota dan anak berhasil disimpan (commit) ke database.")
    except pymysql.MySQLError as e:
        print(f"ERROR: Terjadi kesalahan saat menyimpan data: {e}")
        conn.rollback()
        return "Terjadi kesalahan saat menyimpan data. Silakan coba lagi.", 500
    finally:
        cur.close()
        conn.close()

    return redirect('/data')

@app.route('/delete/<string:nik>', methods=['GET'])
def delete(nik):
    """
    Rute untuk menghapus data anggota berdasarkan NIK.
    Juga menghapus semua data anak yang terkait dengan NIK tersebut.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Hapus data anak terlebih dahulu karena ada foreign key constraint
        cur.execute("DELETE FROM data_anak WHERE NIK_orangtua = %s", (nik,))
        print(f"DEBUG: Data anak terkait NIK {nik} dihapus.")
        # Kemudian hapus data anggota
        cur.execute("DELETE FROM data_p WHERE NIK = %s", (nik,))
        print(f"DEBUG: Data anggota NIK {nik} dihapus.")
        conn.commit()
    except pymysql.MySQLError as e:
        print(f"ERROR: Terjadi kesalahan saat menghapus data: {e}")
        conn.rollback()
        return "Terjadi kesalahan saat menghapus data. Silakan coba lagi.", 500
    finally:
        cur.close()
        conn.close()
    return redirect('/data')


# --- Rute DASHBOARD Dimulai Di Sini ---
@app.route('/dashboard')
def dashboard():
    """
    Rute utama untuk menampilkan dashboard.
    Mengambil data statistik awal dari database untuk ditampilkan di grafik.
    Filter akan diterapkan melalui permintaan AJAX terpisah.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # I. Ringkasan Umum Anggota
    cur.execute("SELECT COUNT(NIK) AS total_anggota FROM data_p")
    total_anggota = cur.fetchone()['total_anggota']

    # Anggota berdasarkan jenis kelamin
    cur.execute("SELECT jenis_kelamin, COUNT(*) AS count FROM data_p GROUP BY jenis_kelamin")
    jenis_kelamin_data = cur.fetchall()
    jenis_kelamin_labels = [d['jenis_kelamin'] if d['jenis_kelamin'] else 'Tidak Diketahui' for d in jenis_kelamin_data]
    jenis_kelamin_values = [d['count'] for d in jenis_kelamin_data]

    # Anggota berdasarkan gol. darah
    cur.execute("SELECT gol_darah, COUNT(*) AS count FROM data_p GROUP BY gol_darah")
    gol_darah_data = cur.fetchall()
    gol_darah_labels = [d['gol_darah'] if d['gol_darah'] else 'Tidak Diketahui' for d in gol_darah_data]
    gol_darah_values = [d['count'] for d in gol_darah_data]

    # Anggota berdasarkan agama
    cur.execute("SELECT agama, COUNT(*) AS count FROM data_p GROUP BY agama")
    agama_data = cur.fetchall()
    agama_labels = [d['agama'] if d['agama'] else 'Tidak Diketahui' for d in agama_data]
    agama_values = [d['count'] for d in agama_data]

    # II. Data Geografis
    cur.execute("SELECT kabkota, COUNT(*) AS count FROM data_p GROUP BY kabkota")
    kabkota_data = cur.fetchall()
    kabkota_labels = [d['kabkota'] if d['kabkota'] else 'Tidak Diketahui' for d in kabkota_data]
    kabkota_values = [d['count'] for d in kabkota_data]

    # III. Data Anak
    cur.execute("SELECT COUNT(id) AS total_anak FROM data_anak")
    total_anak = cur.fetchone()['total_anak']

    # Rata-rata Jumlah Anak per Anggota (dari semua anggota, termasuk yang tidak punya anak)
    cur.execute("""
        SELECT
            dp.NIK,
            COUNT(da.id) AS jumlah_anak
        FROM
            data_p dp
        LEFT JOIN
            data_anak da ON dp.NIK = da.NIK_orangtua
        GROUP BY
            dp.NIK
    """)
    anggota_dengan_anak_counts = cur.fetchall()
    total_anggota_for_avg = total_anggota # Gunakan total anggota keseluruhan
    if total_anggota_for_avg > 0:
        total_jumlah_anak_semua_anggota = sum([item['jumlah_anak'] for item in anggota_dengan_anak_counts])
        rata_rata_anak = total_jumlah_anak_semua_anggota / total_anggota_for_avg
    else:
        rata_rata_anak = 0

    # Ambil semua pilihan unik untuk filter
    cur.execute("SELECT DISTINCT agama FROM data_p WHERE agama IS NOT NULL AND agama != '' ORDER BY agama")
    filter_agama_options = [d['agama'] for d in cur.fetchall()]

    cur.execute("SELECT DISTINCT status FROM data_p WHERE status IS NOT NULL AND status != '' ORDER BY status")
    filter_status_options = [d['status'] for d in cur.fetchall()]

    cur.execute("SELECT DISTINCT kabkota FROM data_p WHERE kabkota IS NOT NULL AND kabkota != '' ORDER BY kabkota")
    filter_kabkota_options = [d['kabkota'] for d in cur.fetchall()]

    cur.close()
    conn.close()

    return render_template('dashboard.html',
                           total_anggota=total_anggota,
                           jenis_kelamin_labels=json.dumps(jenis_kelamin_labels),
                           jenis_kelamin_values=json.dumps(jenis_kelamin_values),
                           gol_darah_labels=json.dumps(gol_darah_labels),
                           gol_darah_values=json.dumps(gol_darah_values),
                           agama_labels=json.dumps(agama_labels),
                           agama_values=json.dumps(agama_values),
                           kabkota_labels=json.dumps(kabkota_labels),
                           kabkota_values=json.dumps(kabkota_values),
                           total_anak=total_anak,
                           rata_rata_anak=f"{rata_rata_anak:.2f}",
                           filter_agama_options=filter_agama_options,
                           filter_status_options=filter_status_options,
                           filter_kabkota_options=filter_kabkota_options
                           )

@app.route('/dashboard_data')
def dashboard_data():
    """
    Endpoint ini digunakan oleh JavaScript di frontend untuk mendapatkan data dashboard
    berdasarkan filter yang dipilih. Mengembalikan data dalam format JSON.
    """
    filter_agama = request.args.get('agama')
    filter_status = request.args.get('status')
    filter_kabkota = request.args.get('kabkota')

    conn = get_db_connection()
    cur = conn.cursor()

    # Query dasar untuk anggota yang akan difilter
    base_query_anggota = "SELECT NIK, jenis_kelamin, gol_darah, agama, kabkota FROM data_p WHERE 1=1"
    params = []

    if filter_agama:
        base_query_anggota += " AND agama = %s"
        params.append(filter_agama)
    if filter_status:
        base_query_anggota += " AND status = %s"
        params.append(filter_status)
    if filter_kabkota:
        base_query_anggota += " AND kabkota = %s"
        params.append(filter_kabkota)

    cur.execute(base_query_anggota, tuple(params))
    filtered_anggota_data = cur.fetchall()

    # Proses data yang difilter untuk grafik
    jenis_kelamin_filtered = {}
    gol_darah_filtered = {}
    agama_filtered = {}
    kabkota_filtered = {}

    for row in filtered_anggota_data:
        jk = row['jenis_kelamin'] if row['jenis_kelamin'] else 'Tidak Diketahui'
        gd = row['gol_darah'] if row['gol_darah'] else 'Tidak Diketahui'
        ag = row['agama'] if row['agama'] else 'Tidak Diketahui'
        kk = row['kabkota'] if row['kabkota'] else 'Tidak Diketahui'

        jenis_kelamin_filtered[jk] = jenis_kelamin_filtered.get(jk, 0) + 1
        gol_darah_filtered[gd] = gol_darah_filtered.get(gd, 0) + 1
        agama_filtered[ag] = agama_filtered.get(ag, 0) + 1
        kabkota_filtered[kk] = kabkota_filtered.get(kk, 0) + 1

    # Total Anggota setelah filter
    total_anggota_filtered = len(filtered_anggota_data)

    # Total Anak terdata dan Rata-rata Jumlah Anak per Anggota (filtered)
    total_anak_filtered = 0
    if filtered_anggota_data:
        # Kumpulkan semua NIK dari anggota yang sudah difilter
        filtered_parent_niks = [row['NIK'] for row in filtered_anggota_data]
        if filtered_parent_niks:
            # Buat placeholder untuk klausa IN
            placeholders = ', '.join(['%s'] * len(filtered_parent_niks))
            # Ambil total anak hanya dari NIK orang tua yang sudah difilter
            cur.execute(f"SELECT COUNT(id) AS total_count FROM data_anak WHERE NIK_orangtua IN ({placeholders})", tuple(filtered_parent_niks))
            total_anak_filtered = cur.fetchone()['total_count']

    # Hitung rata-rata anak per anggota yang difilter
    if total_anggota_filtered > 0:
        rata_rata_anak_filtered = total_anak_filtered / total_anggota_filtered
    else:
        rata_rata_anak_filtered = 0

    cur.close()
    conn.close()

    response_data = {
        'total_anggota': total_anggota_filtered,
        'jenis_kelamin': {
            'labels': list(jenis_kelamin_filtered.keys()),
            'values': list(jenis_kelamin_filtered.values())
        },
        'gol_darah': {
            'labels': list(gol_darah_filtered.keys()),
            'values': list(gol_darah_filtered.values())
        },
        'agama': {
            'labels': list(agama_filtered.keys()),
            'values': list(agama_filtered.values())
        },
        'kabkota': {
            'labels': list(kabkota_filtered.keys()),
            'values': list(kabkota_filtered.values())
        },
        'total_anak': total_anak_filtered,
        'rata_rata_anak': f"{rata_rata_anak_filtered:.2f}"
    }

    return json.dumps(response_data)

@app.route('/export_dashboard_csv')
def export_dashboard_csv():
    """
    Endpoint untuk mengunduh laporan CSV dari data anggota yang ditampilkan (difilter jika ada filter).
    """
    filter_agama = request.args.get('agama')
    filter_status = request.args.get('status')
    filter_kabkota = request.args.get('kabkota')

    conn = get_db_connection()
    cur = conn.cursor()

    query = "SELECT * FROM data_p WHERE 1=1"
    params = []

    if filter_agama:
        query += " AND agama = %s"
        params.append(filter_agama)
    if filter_status:
        query += " AND status = %s"
        params.append(filter_status)
    if filter_kabkota:
        query += " AND kabkota = %s"
        params.append(filter_kabkota)

    cur.execute(query, tuple(params))
    data = cur.fetchall()

    cur.close()
    conn.close()

    if not data:
        return "Tidak ada data untuk diekspor dengan filter yang dipilih.", 404

    # Buat header CSV
    headers = list(data[0].keys())

    si = io.StringIO() # Gunakan StringIO untuk membuat file di memori
    cw = csv.writer(si)

    cw.writerow(headers) # Tulis header
    for row in data:
        # Pastikan semua nilai dikonversi ke string untuk menghindari error CSV
        cw.writerow([str(row[key]) if row[key] is not None else '' for key in headers])

    output = si.getvalue()
    si.close()

    response = Response(output, mimetype='text/csv')
    response.headers["Content-Disposition"] = "attachment; filename=laporan_anggota_dashboard.csv"
    return response

if __name__ == '__main__':
    app.run(debug=True)