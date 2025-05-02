import os

from kys_in_rest.beer.parse_beer import parse_style, parse_name
from kys_in_rest.core.tg_utils import TgFeature, SendTgMessageInterrupt, AskForData
from kys_in_rest.tg.entities.input_tg_msg import InputTgMsg


class AddNewBeer(TgFeature):

    def do(
        self,
        text: str | None,
        tg_user_id: int,
        msg: InputTgMsg | None = None,
    ) -> str:
        if int(tg_user_id) != int(os.environ["TG_ADMIN"]):
            raise SendTgMessageInterrupt("Тебе нельзя")

        if not text:
            raise AskForData("Скинь пост про пиво")

        # todo ask for name
        name = "пиво"
        # name = parse_name(msg.text)

        style = parse_style(msg.text)
        return f"🍺 [{msg.forward_channel_name} — {name} • _{style}_]({msg.forward_link})"
