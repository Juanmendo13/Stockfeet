from __future__ import annotations

from dataclasses import dataclass

from stockfeet.profile import Profile


@dataclass(frozen=True)
class Skin:
    id: str
    name: str
    kind: str  # board | pieces
    price: int
    description: str


BOARD_SKINS: list[Skin] = [
    Skin("classic", "Classic Wood", "board", 0, "Default tournament look"),
    Skin("ocean", "Ocean", "board", 120, "Blue waves and sand"),
    Skin("forest", "Forest", "board", 140, "Moss and bark"),
    Skin("midnight", "Midnight", "board", 180, "Dark arena glow"),
    Skin("coral", "Coral Reef", "board", 200, "Warm coral tiles"),
    Skin("slate", "Slate Pro", "board", 260, "Cool gray competitive"),
    Skin("cherry", "Cherry Wood", "board", 160, "Warm pinkish timber"),
    Skin("walnut", "Walnut", "board", 170, "Deep brown club board"),
    Skin("desert", "Desert", "board", 150, "Sand and clay"),
    Skin("arctic", "Arctic", "board", 190, "Ice and frost"),
    Skin("matcha", "Matcha", "board", 175, "Soft green tea tones"),
    Skin("sunset", "Sunset", "board", 210, "Amber dusk squares"),
    Skin("espresso", "Espresso", "board", 230, "Coffee-house dark wood"),
    Skin("graphite", "Graphite", "board", 240, "Modern charcoal grid"),
    Skin("bamboo", "Bamboo", "board", 155, "Light reed and olive"),
    Skin("crimson", "Crimson Court", "board", 280, "Bold red competitive"),
    Skin("ivory", "Ivory Hall", "board", 250, "Pale cream marble"),
    Skin("neon", "Neon Arena", "board", 320, "High-contrast night board"),
]

PIECE_SKINS: list[Skin] = [
    Skin("classic", "Classic", "pieces", 0, "Standard unicode pieces"),
    Skin("bold", "Bold Ink", "pieces", 100, "High-contrast glyphs"),
    Skin("mono", "Mono", "pieces", 130, "Clean monochrome set"),
    Skin("emerald", "Emerald", "pieces", 220, "Green royal set"),
    Skin("royal", "Royal Gold", "pieces", 300, "Premium gold accents"),
    Skin("ivory", "Ivory & Ebony", "pieces", 180, "Cream whites, deep blacks"),
    Skin("scarlet", "Scarlet", "pieces", 200, "Warm red-black set"),
    Skin("azure", "Azure Steel", "pieces", 210, "Cool blue metal"),
    Skin("copper", "Copper", "pieces", 190, "Oxidized metal tones"),
    Skin("snow", "Snowline", "pieces", 160, "Bright winter whites"),
    Skin("obsidian", "Obsidian", "pieces", 240, "Near-black gloss"),
    Skin("mint", "Mint", "pieces", 170, "Fresh green accents"),
    Skin("amber", "Amber", "pieces", 230, "Honey and smoke"),
    Skin("sakura", "Sakura", "pieces", 260, "Blush pink & charcoal"),
    Skin("cyber", "Cyber", "pieces", 340, "Electric cyan / magenta"),
]

BOARD_COLORS: dict[str, tuple[str, str]] = {
    "classic": ("#f0d9b5", "#b58863"),
    "ocean": ("#d6eaf8", "#2980b9"),
    "forest": ("#e8f5e9", "#3d6b4f"),
    "midnight": ("#4a5568", "#1a202c"),
    "coral": ("#ffe0d1", "#e07a5f"),
    "slate": ("#e2e8f0", "#64748b"),
    "cherry": ("#f3d1c7", "#a65d57"),
    "walnut": ("#e8d5b7", "#6b4423"),
    "desert": ("#f5e6c8", "#c4a35a"),
    "arctic": ("#e8f4f8", "#7ba3b8"),
    "matcha": ("#eef5e0", "#7a9e5c"),
    "sunset": ("#ffe2b8", "#d97706"),
    "espresso": ("#d4b896", "#3e2723"),
    "graphite": ("#cfd4da", "#3a3f46"),
    "bamboo": ("#eef0d8", "#8a9a5b"),
    "crimson": ("#f5d0d0", "#9b1c1c"),
    "ivory": ("#f7f1e3", "#c2b280"),
    "neon": ("#1f2937", "#0ea5e9"),
}

# White / black fill colors for piece glyphs per skin.
PIECE_COLORS: dict[str, tuple[str, str]] = {
    "classic": ("#111111", "#0a0a0a"),
    "bold": ("#000000", "#1b1b1b"),
    "mono": ("#222222", "#444444"),
    "emerald": ("#0b3d2e", "#064e3b"),
    "royal": ("#7a5c00", "#3f2f00"),
    "ivory": ("#f5f0e6", "#1a1a1a"),
    "scarlet": ("#7f1d1d", "#3f0d0d"),
    "azure": ("#0c4a6e", "#082f49"),
    "copper": ("#9a3412", "#5c2410"),
    "snow": ("#f8fafc", "#334155"),
    "obsidian": ("#e5e5e5", "#0a0a0a"),
    "mint": ("#065f46", "#022c22"),
    "amber": ("#b45309", "#451a03"),
    "sakura": ("#9d174d", "#1f2937"),
    "cyber": ("#22d3ee", "#db2777"),
}


def catalog() -> list[Skin]:
    return [*BOARD_SKINS, *PIECE_SKINS]


def get_skin(skin_id: str, kind: str) -> Skin | None:
    pool = BOARD_SKINS if kind == "board" else PIECE_SKINS
    return next((s for s in pool if s.id == skin_id), None)


def board_colors(skin_id: str) -> tuple[str, str]:
    return BOARD_COLORS.get(skin_id, BOARD_COLORS["classic"])


def piece_colors(skin_id: str) -> tuple[str, str]:
    return PIECE_COLORS.get(skin_id, PIECE_COLORS["classic"])


def buy(profile: Profile, skin: Skin) -> str:
    owned = profile.owned_board_skins if skin.kind == "board" else profile.owned_piece_skins
    if skin.id in owned:
        return "Already owned."
    if profile.coins < skin.price:
        return f"Need {skin.price - profile.coins} more FeetCoins."
    profile.coins -= skin.price
    owned.append(skin.id)
    profile.save()
    return f"Purchased {skin.name}!"


def equip(profile: Profile, skin: Skin) -> str:
    owned = profile.owned_board_skins if skin.kind == "board" else profile.owned_piece_skins
    if skin.id not in owned:
        return "Buy it first."
    if skin.kind == "board":
        profile.equipped_board = skin.id
    else:
        profile.equipped_pieces = skin.id
    profile.save()
    return f"Equipped {skin.name}."
