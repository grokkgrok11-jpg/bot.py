OFFER_VARIANTS = {
    "ru": [
        "Пользователь <b>{buyer}</b> предлагает Вам <b>{amount}</b> за подарок <b>{nft_link}.</b>",
        "Пользователь <b>{buyer}</b> хочет купить <b>{nft_link}</b> за <b>{amount}</b>.",
        "<b>{buyer}</b> предлагает <b>{amount}</b> за ваш подарок <b>{nft_link}.</b>",
        "Вам предложили <b>{amount}</b> за <b>{nft_link}</b> от пользователя <b>{buyer}</b>.",
    ],
    "us": [
        "User <b>{buyer}</b> offers You <b>{amount}</b> for gift <b>{nft_link}.</b>",
        "User <b>{buyer}</b> wants to buy <b>{nft_link}</b> for <b>{amount}</b>.",
        "<b>{buyer}</b> offers <b>{amount}</b> for your gift <b>{nft_link}.</b>",
        "You have an offer of <b>{amount}</b> for <b>{nft_link}</b> from <b>{buyer}</b>.",
    ],
    "ua": [
        "Користувач <b>{buyer}</b> пропонує Вам <b>{amount}</b> за подарунок <b>{nft_link}.</b>",
        "Користувач <b>{buyer}</b> хоче купити <b>{nft_link}</b> за <b>{amount}</b>.",
        "<b>{buyer}</b> пропонує <b>{amount}</b> за ваш подарунок <b>{nft_link}.</b>",
        "Вам запропонували <b>{amount}</b> за <b>{nft_link}</b> від користувача <b>{buyer}</b>.",
    ],
}

def get_offer_text(lang: str) -> str:
    variants = OFFER_VARIANTS.get(lang, OFFER_VARIANTS["ru"])
    return random.choice(variants)
