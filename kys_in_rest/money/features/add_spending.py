from typing import Any

from kys_in_rest.core.tg_utils import TgFeature
from kys_in_rest.money.entities.spending import Spending
from kys_in_rest.money.features.spending_repo import SpendingRepo
from kys_in_rest.tg.entities.input_tg_msg import InputTgMsg


class AddSpending(TgFeature):
    def __init__(self, spending_repo: SpendingRepo):
        self.spending_repo = spending_repo

    def do(self, msg: InputTgMsg) -> str | tuple[str, dict[str, Any]]:
        text = msg.text

        try:
            amount, comment = text.split()
        except ValueError:
            return "Нужно прислать в формате `/spend 100 пятерка`"

        spending = Spending(
            amount=amount,
            comment=comment,
        )
        self.spending_repo.add_spending(spending)
        return "Записал 👌"
