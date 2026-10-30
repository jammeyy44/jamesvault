"""
Ask Paydora what it knows about the latest cashouts. Run on the server (virtualenv active, from the GameAPI folder):

    python paydora_check.py          # the last 10 cashouts
    python paydora_check.py 25       # one cashout by its number (WD-25)

For each cashout it prints what OUR site recorded and what PAYDORA answers for that order, so you can tell at once whether the
payout request really exists there. It never prints keys.
"""
import sys

from app import app
from app.models_site import WithdrawalOrder
from app.services.payments import PaymentError, get_payments, payments_mode


def main():
    with app.app_context():
        mode = payments_mode()
        client = get_payments()
        print(f"Payments mode: {mode}; client: {getattr(client, 'name', None)!r}",
              "(this is the FAKE test client: nothing reaches Paydora. Set PAYDORA_API_KEY in GameAPI/.env)" if getattr(client, "name", "") == "sandbox" else "")
        if client is None:
            return
        q = WithdrawalOrder.query.order_by(WithdrawalOrder.id.desc())
        rows = [WithdrawalOrder.query.get(int(sys.argv[1]))] if len(sys.argv) > 1 else q.limit(10).all()
        for w in rows:
            if w is None:
                print("No such cashout.")
                continue
            print(f"\nWD-{w.id}: ${w.amount_cents / 100:,.2f} via {w.method_name} | our status: {w.status} | sandbox: {w.sandbox}")
            print(f"  our note: {w.note or '-'}")
            if not w.provider_withdrawal_id:
                print("  Never sent to Paydora (no provider id recorded). Approve it, or read the note above for why it was refused.")
                continue
            print(f"  provider id: {w.provider_withdrawal_id}  reference: {w.reference_id}")
            try:
                remote = client.get_withdrawal(w.provider_withdrawal_id)
                print(f"  PAYDORA says: status={remote.get('status')} amount={remote.get('amount')} reference={remote.get('referenceId')} "
                      f"createdAt={remote.get('createdAt')} processedAt={remote.get('processedAt')} failedAtProvider={remote.get('failedAtProvider')}")
            except PaymentError as e:
                print(f"  Paydora could not be asked or has no such order: {e} {getattr(e, 'detail', '') or ''}")
            except Exception as e:  # sandbox client has no query
                print(f"  could not query Paydora: {type(e).__name__}")


if __name__ == "__main__":
    main()
