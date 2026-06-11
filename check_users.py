"""check_users.py — Quick script to see all registered users"""
import database as db

conn = db.get_connection()
rows = conn.execute("""
    SELECT id, username, email, role, created_at
    FROM users
    ORDER BY created_at DESC
""").fetchall()
conn.close()

print(f"\n{'='*70}")
print(f"REGISTERED USERS — {len(rows)} total")
print('='*70)
for r in rows:
    print(f"ID: {r['id']:<3} | @{r['username']:<15} | {r['email']:<30} | {r['role']:<10} | {r['created_at']}")
print()