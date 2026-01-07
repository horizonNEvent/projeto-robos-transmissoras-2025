from app.backend.database import SessionLocal, engine
from app.backend import models, auth_utils
from sqlalchemy import text

def debug_users():
    db = SessionLocal()
    try:
        # 1. Verifica se a tabela existe
        try:
            db.execute(text("SELECT 1 FROM users LIMIT 1"))
            print("✅ Tabela 'users' existe.")
        except Exception as e:
            print(f"❌ Tabela 'users' NÃO parece existir ou erro de acesso: {e}")
            # Tenta criar
            models.Base.metadata.create_all(bind=engine)
            print("   Tentativa de criar tabelas executada.")

        # 2. Lista usuários
        users = db.query(models.User).all()
        print(f"📋 Usuários encontrados: {len(users)}")
        for u in users:
            print(f"   - ID: {u.id} | User: {u.username} | Active: {u.is_active}")

        if not users:
            print("⚠️ Nenhum usuário encontrado! Criando BRUNO...")
            new_user = models.User(
                username="BRUNO",
                hashed_password=auth_utils.get_password_hash("admin"),
                email="admin@aete.com.br"
            )
            db.add(new_user)
            db.commit()
            print("✅ Usuário BRUNO criado com sucesso.")
        else:
            # Verifica se BRUNO existe
            bruno = db.query(models.User).filter(models.User.username == "BRUNO").first()
            if bruno:
                print("ℹ️ Usuário BRUNO já existe. Resetando senha para 'admin' para garantir...")
                bruno.hashed_password = auth_utils.get_password_hash("admin")
                db.commit()
                print("✅ Senha de BRUNO resetada para 'admin'.")

    except Exception as e:
        print(f"❌ Erro fatal no script de debug: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    debug_users()
