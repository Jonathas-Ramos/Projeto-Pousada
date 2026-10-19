import hashlib
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.database import initialize, transaction
from backend import clock
from backend.main import app
from backend.security import hash_password


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("COLONIA_DB", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("COLONIA_SECURE_COOKIE", "0")
    with TestClient(app) as test:
        with transaction(write=True) as db:
            db.execute("INSERT INTO usuarios(id,nome,login,senha_hash) VALUES (1,'Recepção Teste','teste',?)", (hash_password('SenhaTeste123!'),))
            token_hash=hashlib.sha256(b'token-de-teste').hexdigest()
            db.execute("INSERT INTO sessoes VALUES (?,1,'csrf-teste',?)",(token_hash,int(time.time())+3600))
        test.cookies.set('colonia_session','token-de-teste')
        test.headers['X-CSRF-Token']='csrf-teste'
        yield test


def guest_data():
    return dict(nome="Hóspede de Teste",cpf="52998224725",nascimento="1990-01-01",email="teste@example.com",telefone="11999999999",
        endereco=dict(cep="01001000",logradouro="Rua Teste",numero="1",bairro="Centro",cidade="Teste",estado="SP"))


def room_payload(client, room_id=1):
    room=client.get(f'/api/quartos/{room_id}').json()
    for key in ('id','valor_diaria','ocupado','situacao_atual'):
        room.pop(key,None)
    return room


@pytest.fixture
def base(client):
    h=client.post('/api/hospedes',json=guest_data()); assert h.status_code==201,h.text
    room=room_payload(client)
    q=client.put('/api/quartos/1',json={**room,'capacidade':3}); assert q.status_code==200,q.text
    return dict(hospede_id=h.json()['id'],quarto_id=q.json()['id'],entrada=clock.today().isoformat(),saida=(clock.today()+timedelta(days=2)).isoformat(),acompanhantes=[{"nome":"Pessoa Acompanhante"}],desconto=0)


def create(client,data):
    result=client.post('/api/reservas',json=data)
    assert result.status_code==201,result.text
    return result.json()


def test_fixed_room_inventory_and_occupancy(client,base):
    rooms=client.get('/api/quartos').json()
    assert len(rooms)==14
    assert [(r['andar'],r['numero']) for r in rooms]==[(floor,floor*100+number) for floor in (1,2) for number in range(1,8)]
    assert all(r['predio']==1 and r['situacao_atual']=='LIVRE' for r in rooms)
    assert rooms[1]['capacidade']==2 and rooms[1]['valor_diaria']==100
    assert all(r['valor_diaria']==120 for r in rooms[7:])
    assert client.get('/api/categorias').status_code==404
    assert 'categoria_id' not in rooms[0]
    assert client.put('/api/quartos/1',json={**room_payload(client),'valor_diaria':999}).status_code==422
    assert client.post('/api/quartos',json=room_payload(client)).status_code==409
    assert client.delete('/api/quartos/1').status_code==409
    booked=create(client,base)
    assert client.get('/api/quartos').json()[0]['situacao_atual']=='LIVRE'  # Confirmada, mas ainda sem check-in.
    assert client.patch(f"/api/reservas/{booked['id']}/check-in").status_code==200
    assert client.get('/api/quartos').json()[0]['situacao_atual']=='OCUPADO'
    assert client.patch(f"/api/reservas/{booked['id']}/check-out").status_code==200
    assert client.get('/api/quartos').json()[0]['situacao_atual']=='LIVRE'
    room2=room_payload(client,2)
    assert client.put('/api/quartos/2',json={**room2,'status':'MANUTENCAO'}).status_code==200
    assert client.get('/api/quartos/2').json()['situacao_atual']=='MANUTENCAO'
    assert client.put('/api/quartos/2',json={**room2,'ativo':False}).status_code==200
    assert client.get('/api/quartos/2').json()['situacao_atual']=='INATIVO'
    initialize()
    assert len(client.get('/api/quartos').json())==14
    assert client.get('/api/quartos/1').json()['valor_diaria']==100
    assert client.get('/api/quartos/1').json()['capacidade']==3
    assert client.get('/api/quartos/2').json()['situacao_atual']=='INATIVO'


def test_demo_uses_preexisting_inventory(client):
    from manage import demo
    demo()
    assert len(client.get('/api/quartos').json())==14
    rooms={r['id']:r['numero'] for r in client.get('/api/quartos').json()}
    bookings=client.get('/api/reservas').json()['items']
    assert {rooms[r['quarto_id']] for r in bookings}=={101,201}
    assert {r['valor_diaria'] for r in bookings}=={100,120}


def test_migration_removes_categories_without_losing_reservation(tmp_path,monkeypatch):
    path=tmp_path/'legacy.sqlite3'
    schema=(Path(__file__).parents[1]/'backend'/'schema.sql').read_text(encoding='utf-8')
    legacy=schema.replace('CREATE TABLE IF NOT EXISTS quartos (',
        "CREATE TABLE IF NOT EXISTS categorias (id INTEGER PRIMARY KEY, nome TEXT NOT NULL UNIQUE, descricao TEXT NOT NULL DEFAULT '', ativo INTEGER NOT NULL DEFAULT 1);\nCREATE TABLE IF NOT EXISTS quartos (")
    legacy=legacy.replace(' andar INTEGER NOT NULL DEFAULT 0,\n capacidade',
        ' andar INTEGER NOT NULL DEFAULT 0, categoria_id INTEGER NOT NULL REFERENCES categorias(id),\n capacidade')
    assert legacy!=schema and 'categoria_id' in legacy
    db=sqlite3.connect(path)
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript(legacy)
    db.execute("INSERT INTO categorias(id,nome) VALUES (1,'Padrão')")
    db.execute("INSERT INTO hospedes(id,nome,cpf,nascimento,email,telefone) VALUES (1,'Teste','52998224725','1990-01-01','teste@example.com','11999999999')")
    db.execute("INSERT INTO quartos(id,numero,predio,andar,categoria_id,capacidade,diaria_centavos) VALUES (1,101,1,1,1,2,10000)")
    db.execute("INSERT INTO quartos(id,numero,predio,andar,categoria_id,capacidade,diaria_centavos) VALUES (2,201,1,2,1,2,10000)")
    db.execute("""INSERT INTO reservas(id,codigo,hospede_id,quarto_id,entrada,saida,quantidade,diaria_centavos,total_centavos,status)
        VALUES (1,'COL-LEGACY',1,2,'2026-10-19','2026-10-20',1,10000,10000,'HOSPEDADA')""")
    db.commit()
    db.close()
    monkeypatch.setenv('COLONIA_DB',str(path))
    initialize()
    db=sqlite3.connect(path)
    assert db.execute('SELECT name FROM sqlite_master WHERE name=?',('categorias',)).fetchone() is None
    assert db.execute('SELECT diaria_centavos FROM quartos WHERE id=2').fetchone()[0]==12000
    assert db.execute('SELECT quarto_id,diaria_centavos,status FROM reservas WHERE id=1').fetchone()==(2,10000,'HOSPEDADA')
    assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
    db.close()
    initialize()


def test_auth_csrf_logout_and_password(client):
    client.cookies.clear()
    assert client.get('/api/hospedes').status_code==401
    response=client.post('/api/auth/login',json={'login':'teste','senha':'SenhaTeste123!'})
    assert response.status_code==200
    assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=strict' in response.headers['set-cookie']
    assert client.post('/api/hospedes',json=guest_data()).status_code==403
    client.headers['X-CSRF-Token']=response.json()['csrf']
    assert client.post('/api/hospedes',json=guest_data()).status_code==201
    assert client.put('/api/auth/senha',json={'senha_atual':'SenhaTeste123!','nova_senha':'OutraSenha123!'}).status_code==200
    assert client.get('/api/auth/me').status_code==401
    response=client.post('/api/auth/login',json={'login':'teste','senha':'OutraSenha123!'})
    assert response.status_code==200
    client.headers['X-CSRF-Token']=response.json()['csrf']
    assert client.post('/api/auth/logout').status_code==200
    assert client.get('/api/auth/me').status_code==401


def test_login_rate_limit(client):
    for _ in range(10):
        assert client.post('/api/auth/login',json={'login':'teste','senha':'incorreta'}).status_code==401
    assert client.post('/api/auth/login',json={'login':'teste','senha':'incorreta'}).status_code==429


def test_guest_crud_address_cpf_and_privacy(client):
    data=guest_data()
    bad={**data,'cpf':'11111111111'}
    response=client.post('/api/hospedes',json=bad)
    assert response.status_code==422 and '11111111111' not in response.text
    created=client.post('/api/hospedes',json=data).json()
    assert client.post('/api/hospedes',json=data).status_code==409
    assert '52998224725' not in client.get('/api/hospedes').text
    assert client.get(f"/api/hospedes/{created['id']}").json()['endereco']['cidade']=='Teste'
    data['endereco']['cidade']='Cidade Nova'
    assert client.put(f"/api/hospedes/{created['id']}",json=data).status_code==200
    assert client.delete(f"/api/hospedes/{created['id']}").status_code==200
    assert client.get(f"/api/hospedes/{created['id']}").status_code==404


def test_booking_price_companions_and_lifecycle(client,base):
    base['desconto']=10.15
    r=create(client,base)
    assert r['valor_total']==189.85 and r['quantidade']==2
    assert r['acompanhantes'][0]['nome']=='Pessoa Acompanhante'
    rid=r['id']
    assert client.post(f'/api/reservas/{rid}/pagamentos',json={'valor':100,'forma':'PIX'}).status_code==201
    assert client.post(f'/api/reservas/{rid}/pagamentos',json={'valor':91,'forma':'PIX'}).status_code==409
    assert client.patch(f'/api/reservas/{rid}/check-out').status_code==409
    assert client.patch(f'/api/reservas/{rid}/check-in').status_code==200
    assert client.put(f'/api/reservas/{rid}',json=base).status_code==409
    assert client.patch(f'/api/reservas/{rid}/cancelar').status_code==409
    assert client.patch(f'/api/reservas/{rid}/check-out').status_code==200
    assert client.get(f'/api/reservas/{rid}').json()['valor_total']==189.85
    assert client.post(f'/api/reservas/{rid}/pagamentos',json={'valor':89.85,'forma':'DINHEIRO'}).status_code==201
    assert client.get(f'/api/reservas/{rid}').json()['saldo']==0


def test_conflict_and_checkout_boundary(client,base):
    create(client,base)
    assert client.post('/api/reservas',json=base).status_code==409
    later={**base,'entrada':base['saida'],'saida':(clock.today()+timedelta(days=4)).isoformat()}
    assert client.post('/api/reservas',json=later).status_code==201
    available=client.get('/api/quartos/disponiveis',params={'entrada':base['entrada'],'saida':base['saida'],'pessoas':2}).json()
    assert len(available)==13 and base['quarto_id'] not in {room['id'] for room in available}


@pytest.mark.parametrize('change',[
    {'saida':clock.today().isoformat()},
    {'entrada':(clock.today()-timedelta(days=1)).isoformat()},
    {'acompanhantes':[{'nome':'Acompanhante Teste'}]*3},
    {'desconto':999},
    {'desconto':-1},
    {'desconto':1.001},
])
def test_invalid_business_inputs(client,base,change):
    assert client.post('/api/reservas',json={**base,**change}).status_code in (409,422)
    assert client.get('/api/reservas').json()['total']==0


def test_room_protection_and_fixed_floor_price(client,base):
    r=create(client,base)
    room=room_payload(client)
    assert client.put('/api/quartos/1',json={**room,'valor_diaria':999}).status_code==422
    edited=client.put(f"/api/reservas/{r['id']}",json=base)
    assert edited.status_code==200 and edited.json()['valor_total']==200
    assert client.put('/api/quartos/1',json={**room,'capacidade':1}).status_code==409
    assert client.put('/api/quartos/1',json={**room,'status':'MANUTENCAO'}).status_code==409
    assert client.delete('/api/quartos/1').status_code==409
    assert client.delete('/api/hospedes/1').status_code==409


def test_room_identity_stays_fixed_after_any_reservation(client,base):
    room=room_payload(client)
    for change in ({'numero':102},{'predio':2},{'andar':2}):
        assert client.put('/api/quartos/1',json={**room,**change}).status_code==409
    booked=create(client,base)
    for change in ({'numero':102},{'predio':2},{'andar':2}):
        response=client.put('/api/quartos/1',json={**room,**change})
        assert response.status_code==409 and 'planta' in response.json()['detail']
    assert client.get(f"/api/reservas/{booked['id']}").json()['quarto_numero']==101
    assert client.delete(f"/api/reservas/{booked['id']}").status_code==200
    assert client.put('/api/quartos/1',json={**room,'numero':102}).status_code==409
    historic=client.get(f"/api/reservas/{booked['id']}").json()
    assert historic['status']=='CANCELADA' and (historic['predio'],historic['quarto_numero'])==(1,101)


def test_cancel_refund_and_preserved_history(client,base):
    r=create(client,base)
    pay=client.post(f"/api/reservas/{r['id']}/pagamentos",json={'valor':50,'forma':'CARTAO'}).json()
    assert client.delete(f"/api/reservas/{r['id']}").status_code==409
    assert client.post(f"/api/pagamentos/{pay['id']}/estornar",json={'motivo':'Devolução confirmada','confirmado':True}).status_code==200
    assert client.delete(f"/api/reservas/{r['id']}").status_code==200
    assert client.get(f"/api/reservas/{r['id']}").json()['status']=='CANCELADA'
    assert client.delete('/api/hospedes/1').status_code==200
    assert client.get('/api/hospedes/1').json()['ativo']==0


def test_update_cannot_reduce_below_paid(client,base):
    r=create(client,base)
    client.post(f"/api/reservas/{r['id']}/pagamentos",json={'valor':200,'forma':'PIX'})
    assert client.put(f"/api/reservas/{r['id']}",json={**base,'desconto':100}).status_code==409
    assert client.get(f"/api/reservas/{r['id']}").json()['valor_total']==200


def test_future_checkin_and_overstay(client,base):
    future={**base,'entrada':(clock.today()+timedelta(days=2)).isoformat(),'saida':(clock.today()+timedelta(days=3)).isoformat()}
    r=create(client,future)
    assert client.patch(f"/api/reservas/{r['id']}/check-in").status_code==409
    current=create(client,base)
    with transaction(write=True) as db:
        db.execute("UPDATE reservas SET status='HOSPEDADA',entrada=?,saida=? WHERE id=?",((clock.today()-timedelta(days=2)).isoformat(),clock.today().isoformat(),current['id']))
    assert client.post('/api/reservas',json={**base,'entrada':(clock.today()+timedelta(days=4)).isoformat(),'saida':(clock.today()+timedelta(days=5)).isoformat()}).status_code==409


def test_brazil_calendar_at_utc_day_boundary(client,base,monkeypatch):
    class FrozenDateTime:
        instant=datetime(2030,1,2,1,30,tzinfo=timezone.utc)

        @classmethod
        def now(cls,tz=None):
            return cls.instant.astimezone(tz)

    monkeypatch.setattr(clock,'datetime',FrozenDateTime)
    assert clock.today().isoformat()=='2030-01-01'
    data={**base,'entrada':'2030-01-01','saida':'2030-01-02'}
    booked=create(client,data)
    assert booked['id'] in [item['id'] for item in client.get('/api/dashboard').json()['entradas']]
    checked=client.patch(f"/api/reservas/{booked['id']}/check-in")
    assert checked.status_code==200 and checked.json()['checkin_em'].startswith('2030-01-01T22:30:00-03:00')
    FrozenDateTime.instant=datetime(2030,1,2,3,30,tzinfo=timezone.utc)
    assert clock.today().isoformat()=='2030-01-02'
    assert booked['id'] in [item['id'] for item in client.get('/api/dashboard').json()['saidas']]
    future={**base,'entrada':'2030-01-04','saida':'2030-01-05'}
    assert client.post('/api/reservas',json=future).status_code==409


def test_concurrent_reservations(client,base):
    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(lambda _:client.post('/api/reservas',json=base).status_code,range(2)))
    assert sorted(results)==[201,409]
    assert client.get('/api/reservas').json()['total']==1


def test_concurrent_payments(client,base):
    r=create(client,base)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(lambda _:client.post(f"/api/reservas/{r['id']}/pagamentos",json={'valor':150,'forma':'PIX'}).status_code,range(2)))
    assert sorted(results)==[201,409]


def test_security_headers_openapi_and_injection(client,base):
    response=client.get('/')
    assert response.status_code==200 and "script-src 'self'" in response.headers['content-security-policy']
    assert client.get('/api/hospedes',params={'q':"' OR 1=1 --"}).json()['total']==0
    assert client.get('/api/openapi.json').status_code==200
    assert client.get('/api/health').json()['status']=='ok'
    assert client.post('/api/reservas',json={**base,'valor_total':0}).status_code==422
    assert client.get('/api/auditoria').status_code==200


def test_performance_1000_guests_and_reservations(client,base):
    from statistics import quantiles
    from time import perf_counter
    with transaction(write=True) as db:
        for i in range(1,1000):
            # Fixture de volume isolada: não são CPFs de pessoas reais nem dados de produção.
            guest_id=db.execute("INSERT INTO hospedes(nome,cpf,nascimento,email,telefone) VALUES (?,?,?, ?,?)",
                (f'Volume {i:04}',f'{i:011}','1990-01-01','volume@example.com','11999999999')).lastrowid
            db.execute("INSERT INTO enderecos(hospede_id,cep,logradouro,numero,bairro,cidade,estado) VALUES (?,?,?,?,?,?,?)",
                (guest_id,'01001000','Rua Volume','1','Centro','Teste','SP'))
        for i in range(1000):
            start=clock.today()+timedelta(days=i)
            db.execute("""INSERT INTO reservas(codigo,hospede_id,quarto_id,entrada,saida,quantidade,diaria_centavos,total_centavos)
                VALUES (?,?,1,?,?,1,10000,10000)""",(f'VOLUME-{i}',i+1,start.isoformat(),(start+timedelta(days=1)).isoformat()))
    timings=[]
    for _ in range(10):
        for url in ['/api/hospedes','/api/reservas','/api/dashboard']:
            start=perf_counter()
            assert client.get(url).status_code==200
            timings.append(perf_counter()-start)
    p95=quantiles(timings,n=20)[18]
    print(f'\nRNF04: 1000 hóspedes + 1000 reservas; 30 consultas; p95={p95:.3f}s; máximo={max(timings):.3f}s')
    assert max(timings)<2
