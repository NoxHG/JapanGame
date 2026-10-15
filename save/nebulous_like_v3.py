"""
Protótipo estilo Nebulous - v3 (roguelike frenético, só formas geométricas)

Controles:
  W A S D ........ mover
  ESPAÇO ......... dash (gasta energia)
  Botão esquerdo . atirar (segura pra metralhar)
  Botão direito .. pulso (apaga tiros inimigos e quebra escudos, gasta energia)
  Q / roda mouse . trocar de arma (armas vêm de perks)
  ESC ............ pausar
  R .............. reiniciar (quando morrer)

Teste (atalhos de debug):
  F1 ............. força o modo "sede de sangue"
  F2 ............. mata todos os inimigos da onda

Instalar: pip install pygame
"""
import math
import random
import sys
from array import array

import pygame
from pygame import Vector2

pygame.mixer.pre_init(44100, -16, 1, 512)
pygame.init()

# ================================================================= tela
W, H = 1280, 720  # resolução interna (o jogo é escalado pra janela)
SIZES = [(960, 540), (1280, 720), (1600, 900), (1920, 1080)]
settings = {"size": 1, "full": False}
display = pygame.display.set_mode(SIZES[settings["size"]])
pygame.display.set_caption("Nebulous-like")
canvas = pygame.Surface((W, H))
screen = canvas
overlay = pygame.Surface((W, H), pygame.SRCALPHA)
spike_layer = pygame.Surface((W, H), pygame.SRCALPHA)
iris_layer = pygame.Surface((W, H), pygame.SRCALPHA)
dim_layer = pygame.Surface((W, H), pygame.SRCALPHA)
view = {"scale": 1.0, "ox": 0, "oy": 0}
clock = pygame.time.Clock()

font = pygame.font.SysFont("arial", 16)
font_b = pygame.font.SysFont("arial", 18, bold=True)
font_m = pygame.font.SysFont("arial", 26, bold=True)
big_font = pygame.font.SysFont("arial", 50, bold=True)
title_font = pygame.font.SysFont("arial", 76, bold=True)
dmg_font = pygame.font.SysFont("arial", 44, bold=True)


def apply_display():
    global display
    if settings["full"]:
        display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        display = pygame.display.set_mode(SIZES[settings["size"]])


def present(shake=0.0):
    dw, dh = display.get_size()
    sc = min(dw / W, dh / H)
    sw, sh = int(W * sc), int(H * sc)
    ox, oy = (dw - sw) // 2, (dh - sh) // 2
    view["scale"], view["ox"], view["oy"] = sc, ox, oy
    sx = int(random.uniform(-shake, shake)) if shake > 0 else 0
    sy = int(random.uniform(-shake, shake)) if shake > 0 else 0
    display.fill((0, 0, 0))
    if (sw, sh) == (W, H):
        display.blit(canvas, (ox + sx, oy + sy))
    else:
        display.blit(pygame.transform.scale(canvas, (sw, sh)), (ox + int(sx * sc), oy + int(sy * sc)))
    pygame.display.flip()


def get_mouse():
    mx, my = pygame.mouse.get_pos()
    return Vector2((mx - view["ox"]) / view["scale"], (my - view["oy"]) / view["scale"])


# ================================================================= cores
WHITE = (245, 245, 245)
ARMOR_RED = (255, 0, 0)
BLUE = (80, 170, 255)
BLOODLUST_BG = (62, 0, 14)
SPIKE_BASE = 18
SPIKE_BL = 38
ROOM_TIME = 300   # 5 minutos
BOSS_TIME = 600   # 10 minutos
AMBIENT = 30      # partículas de poeira no fundo (0 desliga)


# ================================================================= utilidades
def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def wrap_angle(a):
    return (a + math.pi) % math.tau - math.pi


def from_angle(a):
    return Vector2(math.cos(a), math.sin(a))


def lerp_color(a, b, t):
    t = clamp(t, 0, 1)
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ellipse_points(cx, cy, rx, ry, angle, n=28):
    ca, sa = math.cos(angle), math.sin(angle)
    pts = []
    for i in range(n):
        t = i / n * math.tau
        x, y = math.cos(t) * rx, math.sin(t) * ry
        pts.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return pts


def draw_center(surf, txt, fnt, color, pos):
    img = fnt.render(txt, True, color)
    surf.blit(img, img.get_rect(center=(int(pos[0]), int(pos[1]))))


def wrap_text(txt, fnt, width):
    words, lines, cur = txt.split(), [], ""
    for w_ in words:
        test = (cur + " " + w_).strip()
        if fnt.size(test)[0] <= width:
            cur = test
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


# ================================================================= áudio (sons sintetizados)
SND = {}
SR = 44100
CH = 1
_last_play = {}
SFX_GAP = {"shoot": 25, "hit": 30, "shield_hit": 30, "eshoot": 40}


def synth(f0, f1, dur, vol=0.3, wave="sine", noise=0.0, decay=3.0):
    n = int(SR * dur)
    out = array("h")
    phase = 0.0
    for i in range(n):
        t = i / n
        f = f0 + (f1 - f0) * t
        phase += f / SR
        ph = phase % 1.0
        if wave == "sine":
            s = math.sin(math.tau * ph)
        elif wave == "square":
            s = 1.0 if ph < 0.5 else -1.0
        elif wave == "saw":
            s = 2 * ph - 1
        else:
            s = random.uniform(-1, 1)
        if noise:
            s = s * (1 - noise) + random.uniform(-1, 1) * noise
        env = math.exp(-decay * t) * min(1.0, i / (SR * 0.004))
        v = int(32767 * vol * s * env)
        out.append(v)
        if CH == 2:
            out.append(v)
    return pygame.mixer.Sound(buffer=out.tobytes())


def init_audio():
    global SR, CH
    try:
        info = pygame.mixer.get_init()
        if not info or info[1] != -16:
            return
        SR, CH = info[0], info[2]
        pygame.mixer.set_num_channels(20)
        SND["shoot"] = synth(900, 300, 0.07, 0.10, "square", decay=4)
        SND["shoot_heavy"] = synth(320, 80, 0.18, 0.2, "saw", noise=0.2, decay=4)
        SND["eshoot"] = synth(500, 250, 0.09, 0.07, "square", decay=4)
        SND["dash"] = synth(200, 1300, 0.16, 0.13, "saw", noise=0.4, decay=3)
        SND["hit"] = synth(0, 0, 0.04, 0.12, "noise", decay=6)
        SND["shield_hit"] = synth(1500, 1100, 0.05, 0.10, "sine", decay=5)
        SND["shield_break"] = synth(700, 120, 0.22, 0.18, "square", decay=4)
        SND["armor_break"] = synth(420, 60, 0.2, 0.2, "saw", noise=0.5, decay=4)
        SND["kill"] = synth(0, 0, 0.3, 0.26, "noise", decay=5)
        SND["hurt"] = synth(220, 60, 0.25, 0.28, "saw", decay=4)
        SND["pickup"] = synth(700, 1500, 0.1, 0.18, "sine", decay=4)
        SND["pulse"] = synth(120, 900, 0.3, 0.22, "sine", decay=2.5)
        SND["menu"] = synth(600, 800, 0.05, 0.12, "square", decay=5)
        SND["perk"] = synth(500, 1100, 0.3, 0.22, "sine", decay=2.5)
        SND["bloodlust"] = synth(95, 45, 0.9, 0.28, "saw", noise=0.1, decay=1.2)
        SND["whoosh"] = synth(0, 0, 0.5, 0.12, "noise", decay=2.5)
        SND["boss"] = synth(70, 35, 0.9, 0.32, "saw", decay=1.5)
        SND["zap"] = synth(1800, 200, 0.22, 0.2, "saw", noise=0.3, decay=4)
        SND["boom"] = synth(120, 40, 0.4, 0.3, "saw", noise=0.6, decay=3)
        SND["rocket"] = synth(260, 90, 0.2, 0.14, "saw", noise=0.5, decay=3)
    except Exception as exc:  # sem áudio? tudo bem, o jogo roda sem som
        print("Áudio desativado:", exc)
        SND.clear()


def sfx(name, vol=1.0):
    s = SND.get(name)
    if s is None:
        return
    now = pygame.time.get_ticks()
    if now - _last_play.get(name, -999) < SFX_GAP.get(name, 20):
        return
    _last_play[name] = now
    s.set_volume(vol)
    s.play()


# ================================================================= raridades, perks, armas
# (nome, cor, multiplicador, peso)
RARITIES = [
    ("Comum", (150, 150, 150), 1.0, 40),
    ("Não-Comum", (120, 235, 130), 1.4, 26),
    ("Raro", (110, 200, 255), 1.9, 15),
    ("Raro+", (40, 90, 230), 2.5, 8),
    ("Épico", (180, 90, 255), 3.3, 5),
    ("Épico+", (110, 40, 180), 4.2, 3),
    ("Lendário", (255, 200, 40), 5.5, 1.6),
    ("Mítico", (255, 30, 30), 7.0, 0.9),
    ("Abyssal", (70, 0, 120), 10.0, 0.25),
    ("Exterminador", (255, 255, 255), 15.0, 0.08),
]

# (nome, stat, valor base, texto, formato)   formato: pct | pct1 | int | dec1
PERKS = [
    ("Ferro Quente", "dmg", 0.10, "+{}% de dano", "pct"),
    ("Gatilho Leve", "rate", 0.08, "+{}% cadência de tiro", "pct"),
    ("Pés Leves", "speed", 0.05, "+{}% velocidade", "pct"),
    ("Casco Reforçado", "maxhp", 10, "+{} vida máxima", "int"),
    ("Faísca", "frag", 0.05, "+{}% chance de fragmento", "pct"),
    ("Calmaria", "regen", 0.10, "+{}% recarga de energia", "pct"),
    ("Projétil Veloz", "bspeed", 0.08, "+{}% velocidade do tiro", "pct"),
    ("Dash Eficiente", "dashcost", 0.06, "-{}% custo do dash", "pct"),
    ("Dash Longo", "dashdist", 0.08, "+{}% distância do dash", "pct"),
    ("Regeneração", "hpregen", 0.25, "+{} vida por segundo", "dec1"),
    ("Restauração", "waveheal", 3, "+{} vida a cada onda", "int"),
    ("Vampirismo", "lifesteal", 0.03, "+{}% do dano vira vida", "pct1"),
]

WEAPONS = {
    "pistola": dict(name="Pistola", cd=0.16, pellets=1, spread=0.04, mode="rand", speed=950, dmg=10,
                    pierce=0, bounce=0, life=1.3, snd="shoot", desc="Tiro único e preciso."),
    "metra": dict(name="Metralhadora", cd=0.07, pellets=1, spread=0.14, mode="rand", speed=1000, dmg=5.5,
                  pierce=0, bounce=0, life=1.2, snd="shoot", desc="Chuva de tiros rápidos e imprecisos."),
    "escopeta": dict(name="Escopeta", cd=0.55, pellets=7, spread=0.5, mode="rand", speed=800, dmg=6.5,
                     pierce=0, bounce=0, life=0.5, snd="shoot_heavy", desc="Vários projéteis de curto alcance."),
    "rifle": dict(name="Rifle Perfurante", cd=0.48, pellets=1, spread=0.0, mode="rand", speed=1600, dmg=34,
                  pierce=3, bounce=0, life=1.2, snd="shoot_heavy", desc="Atravessa até 3 alvos."),
    "triplo": dict(name="Tiro Triplo", cd=0.25, pellets=3, spread=0.3, mode="fan", speed=950, dmg=7.5,
                   pierce=0, bounce=0, life=1.2, snd="shoot", desc="Três tiros em leque."),
    "ricochete": dict(name="Ricochete", cd=0.26, pellets=1, spread=0.03, mode="rand", speed=820, dmg=12,
                      pierce=0, bounce=3, life=2.4, snd="shoot", desc="Quica 3 vezes nas paredes."),
    "canhao": dict(name="Canhão", cd=0.85, pellets=1, spread=0.02, mode="rand", speed=620, dmg=48,
                   pierce=1, bounce=0, life=1.6, size=11, snd="shoot_heavy",
                   desc="Projétil grosso e lento. Perfura 1 alvo."),
    "agulha": dict(name="Agulha", cd=0.13, pellets=1, spread=0.02, mode="rand", speed=2300, dmg=11,
                   pierce=1, bounce=0, life=0.8, size=2, line=True, snd="shoot",
                   desc="Projétil fino e super rápido. Perfura 1 alvo."),
    "orbe": dict(name="Orbe Arcano", cd=0.75, pellets=1, spread=0.0, mode="rand", speed=280, dmg=30,
                 pierce=99, bounce=0, life=3.2, size=15, snd="shoot_heavy",
                 desc="Esfera lenta que atravessa tudo."),
    "duplo": dict(name="Disparo Duplo", cd=0.17, pellets=2, spread=0.03, mode="par", gap=16, speed=1000, dmg=7,
                  pierce=0, bounce=0, life=1.2, snd="shoot", desc="Dois tiros paralelos."),
    # drops de boss
    "cajado": dict(name="Cajado Mágico", type="beam", cd=0.75, dmg=24, width=30, pellets=1, spread=0, mode="rand",
                   speed=0, pierce=0, bounce=0, life=0, snd="zap",
                   desc="Raio mágico branco em área, atravessa inimigos."),
    "foguete": dict(name="Lança-Foguetes", type="rocket", cd=1.0, dmg=32, radius=100, max=620, turn=3.4, life=4.5,
                    pellets=1, spread=0, mode="rand", speed=0, pierce=0, bounce=0, snd="rocket",
                    desc="Foguete teleguiado que explode em área."),
}
WEAPON_PERK_KEYS = ["metra", "escopeta", "rifle", "triplo", "ricochete", "canhao", "agulha", "orbe", "duplo"]
BOSS_WEAPON_KEYS = ["cajado", "foguete"]


def fmt_val(v, kind):
    if kind == "pct":
        return str(max(1, round(v * 100)))
    if kind == "pct1":
        return f"{v * 100:.1f}"
    if kind == "int":
        return str(max(1, round(v)))
    return f"{max(0.1, v):.1f}"


def weapon_perk(key, ridx, boss_drop=False):
    wpn = WEAPONS[key]
    return {"kind": "weapon", "name": wpn["name"], "rarity": ridx, "weapon": key,
            "text": "Equipa a arma" + (f" (+{12 * ridx}% de dano)" if ridx else ""),
            "desc": wpn["desc"], "boss_drop": boss_drop}


def roll_perk(mini=False, bonus=0.0, boss_weapon=False):
    weights = [r[3] * (1 + bonus * i) for i, r in enumerate(RARITIES)]
    ridx = random.choices(range(len(RARITIES)), weights=weights)[0]
    mult = RARITIES[ridx][2]
    if boss_weapon:
        return weapon_perk(random.choice(BOSS_WEAPON_KEYS), ridx, True)
    if not mini and random.random() < 0.3:
        return weapon_perk(random.choice(WEAPON_PERK_KEYS), ridx)
    name, stat, base, fmt, kind = random.choice(PERKS)
    value = base * mult * (0.4 if mini else 1.0)
    return {"kind": "stat", "name": ("Mini " if mini else "") + name, "rarity": ridx, "stat": stat,
            "value": value, "text": fmt.format(fmt_val(value, kind)), "desc": ""}


def draw_perk_circle(surf, c, r, perk, t=0.0, filled=True):
    col = RARITIES[perk["rarity"]][1]
    width = 3 if r >= 12 else 2
    pygame.draw.circle(surf, col, c, r, width)
    if filled:
        pygame.draw.circle(surf, col, c, max(2, int(r * 0.42)))
    if perk["rarity"] >= 8:  # Abyssal e Exterminador ganham um brilho extra
        glow = (150, 80, 230) if perk["rarity"] == 8 else (200, 230, 255)
        pulse = 0.5 + 0.5 * math.sin(t * 5)
        pygame.draw.circle(surf, lerp_color((0, 0, 0), glow, 0.4 + 0.6 * pulse), c, r + 3, 1)


# ================================================================= inimigos
def _diamond_guns():
    return [(45 + 90 * k, 45 + 90 * k) for k in range(4)]


ENEMY_TYPES = {
    # pequenos: só armadura + núcleo
    "kami": dict(sides=0, off=0, a=14, armor=22, core=10, cr=0.45, shield=0, move="rush", speed=175, turn=8,
                 guns=[], cost=1.0, min_wave=1, kamikaze=True),
    "dart": dict(sides=3, off=0, a=18, armor=18, core=8, cr=0.34, shield=0, move="rush", speed=255, turn=7,
                 guns=[], cost=1.5, min_wave=3, kamikaze=True),
    "gunner": dict(sides=4, off=0, a=17, armor=32, core=14, cr=0.40, shield=0, move="keep", speed=135, turn=5,
                   guns="aim", charge=1.8, cost=1.5, min_wave=1),
    # médios
    "tank": dict(sides=4, off=45, a=30, armor=130, core=26, cr=0.36, shield=90, move="chase", speed=80, turn=1.4,
                 guns=[(90, 0), (-90, 0)], charge=2.8, cost=3.0, min_wave=4),
    "hex": dict(sides=6, off=0, a=30, armor=110, core=24, cr=0.36, shield=0, move="roam", speed=85, turn=0.6,
                guns=[(30 + 60 * k, 30 + 60 * k) for k in range(6)], charge=3.2, cost=3.0, min_wave=6, spin=True),
    # grande: o losango original
    "diamond": dict(sides=4, off=0, a=46, armor=80, core=60, cr=0.28, shield=120, move="axis", speed=100, turn=1.2,
                    guns=_diamond_guns(), charge=3.0, cost=4.0, min_wave=8),
    # boss
    "boss": dict(sides=4, off=0, a=80, armor=320, core=240, cr=0.28, shield=240, move="axis", speed=75, turn=0.9,
                 guns=_diamond_guns(), charge=2.4, cost=99, min_wave=999, boss=True, spread=[-0.25, 0, 0.25]),
    "boss_orb": dict(sides=0, off=0, a=62, armor=150, core=120, cr=0.3, shield=0, move="custom", speed=300, turn=0,
                     guns=[], cost=99, min_wave=999, boss=True),
    "boss_twin": dict(sides=0, off=0, a=110, armor=1, core=150, cr=0.24, shield=0, move="custom", speed=115, turn=0,
                      guns=[], cost=99, min_wave=999, boss=True),
}


class Enemy:
    custom_contact = False

    def __init__(self, kind, pos, hp_mult=1.0):
        c = ENEMY_TYPES[kind]
        self.kind, self.c = kind, c
        self.pos = Vector2(pos)
        self.a = c["a"]
        self.sides = c["sides"]
        self.boss = c.get("boss", False)
        self.kamikaze = c.get("kamikaze", False)
        self.armor_max = c["armor"] * hp_mult
        self.armor = self.armor_max
        self.shield_max = c.get("shield", 0) * hp_mult
        self.shield = self.shield_max
        self.shield_timer = 0.0
        self.core_max = c["core"] * hp_mult
        self.core = self.core_max
        self.core_r = max(4.0, self.a * c["cr"])
        self.angle = random.uniform(-math.pi, math.pi)
        self.aim = self.angle
        self.flash = 0.0
        self.dead = False
        self.spawn_t = 0.6
        self.phase = random.uniform(0, math.tau)
        self.move_dir = Vector2()
        self.move_timer = random.uniform(0.2, 1.0)
        self.strafe = random.choice((-1, 1))
        self.strafe_t = random.uniform(1.5, 3.0)
        self.target = None
        self.minion_t = 7.0
        self.charge_time = c.get("charge", 3.0)
        self.charge = random.uniform(0, self.charge_time * 0.8)

        # geometria
        self.verts = []
        if self.sides:
            step = math.tau / self.sides
            off = math.radians(c.get("off", 0))
            for k in range(self.sides):
                ang = off + k * step
                self.verts.append((self.a * math.cos(ang), self.a * math.sin(ang)))
            self.apothem = self.a * math.cos(math.pi / self.sides)
        else:
            self.apothem = self.a

        # escudo (com espaço entre ele e o corpo)
        self.gap = 7 + self.a * 0.04
        self.shield_local = []
        self.shield_span = math.radians(70)
        if self.shield_max > 0:
            if self.sides:
                step = math.tau / self.sides
                off = math.radians(c.get("off", 0))
                f = 1 + self.gap / self.apothem
                items = []
                for k in range(self.sides):
                    va = wrap_angle(off + k * step)
                    if abs(va) <= step * 1.01:
                        items.append((va, (self.a * f * math.cos(off + k * step), self.a * f * math.sin(off + k * step))))
                items.sort(key=lambda it: it[0])
                self.shield_local = [p for _, p in items]
                self.shield_span = max(abs(va) for va, _ in items)
            else:
                span = self.shield_span
                rr = self.a + self.gap
                self.shield_local = [(rr * math.cos(-span + 2 * span * i / 14), rr * math.sin(-span + 2 * span * i / 14))
                                     for i in range(15)]

        # armas
        g = c.get("guns", [])
        self.gun_aim = g == "aim"
        self.gun_list = [] if self.gun_aim else [(math.radians(p), math.radians(f)) for p, f in g]
        self.has_guns = self.gun_aim or bool(self.gun_list)

    # ---- geometria
    def boundary_r(self, th):
        if not self.sides:
            return self.a
        step = math.tau / self.sides
        off = math.radians(self.c.get("off", 0))
        k = round((th - off) / step - 0.5)
        phi = off + (k + 0.5) * step
        return self.apothem / max(0.2, math.cos(wrap_angle(th - phi)))

    def inside(self, lx, ly):
        if not self.sides:
            return lx * lx + ly * ly <= self.a * self.a
        n = len(self.verts)
        for i in range(n):
            v1, v2 = self.verts[i], self.verts[(i + 1) % n]
            if (v2[0] - v1[0]) * (ly - v1[1]) - (v2[1] - v1[1]) * (lx - v1[0]) < 0:
                return False
        return True

    def gun_geoms(self, full=False):
        s = 1.0 if full else 0.2 + 0.8 * clamp(self.charge / self.charge_time, 0, 1)
        size = 8 + 0.35 * self.a
        h, w = size * s, size * 0.42 * s
        out = []
        if self.gun_aim:
            rel = wrap_angle(self.aim - self.angle)
            pairs = [(self.aim, self.aim, rel)]
        else:
            pairs = [(self.angle + pa, self.angle + fa, pa) for pa, fa in self.gun_list]
        for wpa, wfa, rel_pa in pairs:
            base = self.pos + from_angle(wpa) * (self.boundary_r(rel_pa) + 3)
            n = from_angle(wfa)
            out.append((base, n, base + n * h, w))
        return out

    # ---- combate
    def break_shield(self):
        if self.shield > 0:
            self.shield = 0
            self.shield_timer = 5.0
            self.flash = 0.1

    def try_hit(self, p, dmg):
        """Retorna um texto descrevendo o que o tiro acertou, ou None se errou."""
        if self.spawn_t > 0 or self.dead:
            return None
        d = p - self.pos
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        lx = d.x * ca + d.y * sa
        ly = -d.x * sa + d.y * ca
        if self.armor > 0:
            if not self.inside(lx, ly):
                return None
            self.flash = 0.08
            if self.shield > 0 and abs(math.atan2(ly, lx)) <= self.shield_span:
                self.shield -= dmg
                if self.shield <= 0:
                    self.break_shield()
                    return "shield_break"
                return "shield_hit"
            self.armor -= dmg
            if self.armor <= 0:
                self.armor = 0
                self.shield = 0
                return "armor_break"
            return "hit"
        if d.length() <= self.core_r + 5:
            self.core -= dmg
            self.flash = 0.08
            if self.core <= 0:
                self.dead = True
                return "kill"
            return "hit"
        return None

    def try_area(self, center, radius, dmg):
        d = center - self.pos
        if d.length() > radius + self.a:
            return None
        dirv = d.normalize() if d.length_squared() > 0 else Vector2(1, 0)
        p = self.pos + dirv * self.a * 0.4 if self.armor > 0 else Vector2(self.pos)
        return self.try_hit(p, dmg)

    def fire(self, game):
        spreads = self.c.get("spread", [0])
        speed = self.c.get("bspeed", 230) * (1.25 if game.bloodlust else 1.0)
        for base, n, tip, w in self.gun_geoms(full=True):
            base_ang = math.atan2(n.y, n.x)
            for s in spreads:
                game.ebullets.append({"p": Vector2(tip), "v": from_angle(base_ang + s) * speed})
        sfx("eshoot", 0.6)

    def update(self, dt, game):
        if self.spawn_t > 0:
            self.spawn_t -= dt
            return
        self.flash = max(0, self.flash - dt)
        bl = game.bloodlust
        k = 1.7 if bl else 1.0
        pl = game.player
        to_p = pl.pos - self.pos
        dist = to_p.length()
        dirp = to_p / dist if dist > 0 else Vector2(1, 0)
        perp = Vector2(-dirp.y, dirp.x)

        # escudo regenera
        if self.shield <= 0 and self.shield_max > 0 and self.armor > 0:
            self.shield_timer -= dt
            if self.shield_timer <= 0:
                self.shield = self.shield_max

        mv = self.c["move"]
        speed = self.c["speed"] * k
        if mv == "rush":
            wob = math.sin(game.t * 3 + self.phase) * 0.35
            v = dirp + perp * wob
            self.pos += v.normalize() * speed * dt
        elif mv == "keep":
            self.strafe_t -= dt
            if self.strafe_t <= 0:
                self.strafe *= -1
                self.strafe_t = random.uniform(1.5, 3.0)
            if dist > 340:
                v = dirp
            elif dist < 230:
                v = -dirp
            else:
                v = perp * self.strafe
            self.pos += v * speed * dt
        elif mv == "chase":
            if dist > 130:
                self.pos += dirp * speed * dt
        elif mv == "roam":
            self.move_timer -= dt
            if self.target is None or self.move_timer <= 0 or self.pos.distance_to(self.target) < 20:
                self.target = Vector2(random.uniform(120, W - 120), random.uniform(120, H - 200))
                self.move_timer = random.uniform(2.0, 3.5)
            d = self.target - self.pos
            if d.length_squared() > 0:
                self.pos += d.normalize() * speed * dt
        elif mv == "axis":
            self.move_timer -= dt
            if self.move_timer <= 0:
                self.move_timer = random.uniform(0.9, 2.0)
                r = random.random()
                if r < 0.12:
                    self.move_dir = Vector2()
                elif r < 0.65:
                    if abs(to_p.x) > abs(to_p.y):
                        self.move_dir = Vector2(1 if to_p.x > 0 else -1, 0)
                    else:
                        self.move_dir = Vector2(0, 1 if to_p.y > 0 else -1)
                else:
                    self.move_dir = random.choice([Vector2(1, 0), Vector2(-1, 0), Vector2(0, 1), Vector2(0, -1)])
            self.pos += self.move_dir * speed * dt

        m = self.a + 44
        nx, ny = clamp(self.pos.x, m, W - m), clamp(self.pos.y, m, H - m)
        if (nx, ny) != (self.pos.x, self.pos.y):
            self.pos.update(nx, ny)
            if mv == "axis":
                self.move_dir = -self.move_dir
            elif mv == "keep":
                self.strafe *= -1

        # rotação
        target_ang = math.atan2(dirp.y, dirp.x)
        if self.c.get("spin"):
            self.angle += 0.8 * k * dt
        else:
            diff = wrap_angle(target_ang - self.angle)
            turn = self.c["turn"] * dt * (1.3 if bl else 1.0)
            self.angle += clamp(diff, -turn, turn)
        if self.gun_aim:
            diff = wrap_angle(target_ang - self.aim)
            self.aim += clamp(diff, -4 * dt, 4 * dt)

        # armas: triângulos crescem devagar, depois atiram
        if self.has_guns:
            self.charge += dt * (2 if bl else 1)
            if self.charge >= self.charge_time:
                self.charge = 0
                self.fire(game)

        # boss chama capangas
        if self.boss:
            self.minion_t -= dt
            if self.minion_t <= 0:
                self.minion_t = 4.5 if bl else 9.0
                game.spawn_minions(self.pos, 2)

    def draw(self, surf, t, bl):
        if self.spawn_t > 0:
            u = 1 - self.spawn_t / 0.6
            pygame.draw.circle(surf, WHITE, self.pos, max(2, int(self.a * (2.2 - 1.4 * u))), 1)
            pygame.draw.circle(surf, WHITE, self.pos, max(1, int(self.core_r * u)))
            return
        ca, sa = math.cos(self.angle), math.sin(self.angle)

        def tw(lx, ly):
            return (self.pos.x + lx * ca - ly * sa, self.pos.y + lx * sa + ly * ca)

        # armas
        for base, n, tip, w in self.gun_geoms():
            tv = Vector2(-n.y, n.x)
            s = clamp(self.charge / self.charge_time, 0, 1)
            pygame.draw.polygon(surf, lerp_color((110, 0, 0), (255, 0, 0), s), [tip, base + tv * w, base - tv * w])

        # corpo
        if self.armor > 0:
            col = (255, 170, 170) if self.flash > 0 else ARMOR_RED
            if self.sides:
                pygame.draw.polygon(surf, col, [tw(*v) for v in self.verts])
            else:
                pygame.draw.circle(surf, col, self.pos, int(self.a))
        else:
            if self.sides:
                pygame.draw.polygon(surf, (140, 0, 0), [tw(*v) for v in self.verts], 2)
            else:
                pygame.draw.circle(surf, (140, 0, 0), self.pos, int(self.a), 2)

        # escudo branco, afastado do corpo
        if self.shield_max > 0 and self.armor > 0:
            pts = [tw(*p) for p in self.shield_local]
            if self.shield > 0:
                pygame.draw.lines(surf, WHITE, False, pts, int(2 + 4 * self.shield / self.shield_max))
            else:
                pygame.draw.lines(surf, (70, 70, 70), False, pts, 1)

        # núcleo (pisca na sede de sangue)
        core_col = WHITE
        if bl and int(t * 12) % 2 == 0:
            core_col = (255, 90, 90)
        if self.flash > 0 and self.armor <= 0:
            core_col = (255, 190, 190)
        pygame.draw.circle(surf, core_col, self.pos, int(self.core_r))
        if self.armor <= 0 and self.a >= 28:
            bw = self.a * 1.1
            r = pygame.Rect(self.pos.x - bw / 2, self.pos.y - self.a - 18, bw, 4)
            pygame.draw.rect(surf, (40, 40, 50), r)
            r.width = int(bw * clamp(self.core / self.core_max, 0, 1))
            pygame.draw.rect(surf, WHITE, r)


BOSS_ORDER = ["boss", "boss_orb", "boss_twin"]
BOSS_NAMES = {"boss": "LOSANGO", "boss_orb": "ORBE", "boss_twin": "GÊMEOS"}


class OrbBoss(Enemy):
    # Boss 2: círculo vermelho com 8 gotas. Fase 2: núcleo expandido que ricocheteia nas paredes.
    custom_contact = True

    def __init__(self, kind, pos, hp_mult=1.0):
        super().__init__(kind, pos, hp_mult)
        self.phase = 1
        self.sub = "expand"
        self.sub_t = 0.0
        self.orbit = 0.0
        self.fire_t = 1.2
        self.burst_t = 4.5
        self.vel = Vector2()
        self.bounces = 0
        self.base_a = self.a
        self.base_core = self.core_r
        self.entering = False

    def drop_centers(self):
        if self.phase == 1:
            r, base = self.a + 16, self.angle
        else:
            r = self.a + (70 if self.sub == "rest" else 34)
            base = self.orbit
        return [(self.pos + from_angle(base + k * math.pi / 4) * r, base + k * math.pi / 4) for k in range(8)]

    def drops_active(self):
        return self.phase == 1 or self.sub != "rest"

    def try_hit(self, p, dmg):
        if self.spawn_t > 0 or self.dead:
            return None
        if self.phase == 1:
            res = Enemy.try_hit(self, p, dmg)
            if self.armor <= 0 and self.phase == 1:
                self.phase, self.sub, self.sub_t, self.entering = 2, "expand", 0.0, True
            return res
        if self.sub == "expand":
            return None
        if self.sub != "rest":  # as gotas girando bloqueiam os tiros
            for c, _ in self.drop_centers():
                if c.distance_to(p) < 14:
                    return "shield_hit"
        if (p - self.pos).length() <= self.a:
            self.core -= dmg * (1.5 if self.sub == "rest" else 1.0)
            self.flash = 0.08
            if self.core <= 0:
                self.dead = True
                return "kill"
            return "hit"
        return None

    def shoot_drops(self, game, spreads):
        spd = 210 * (1.25 if game.bloodlust else 1.0)
        for c, ang in self.drop_centers():
            for s in spreads:
                d = from_angle(ang + s)
                game.ebullets.append({"p": c + d * 22, "v": d * spd})
        sfx("eshoot", 0.6)

    def clamp_arena(self, game):
        m = self.a + game.spike_depth + 10
        self.pos.x = clamp(self.pos.x, m, W - m)
        self.pos.y = clamp(self.pos.y, m, H - m)

    def update(self, dt, game):
        if self.spawn_t > 0:
            self.spawn_t -= dt
            return
        self.flash = max(0, self.flash - dt)
        bl = game.bloodlust
        k = 1.5 if bl else 1.0
        pl = game.player
        if self.entering:
            self.entering = False
            game.shake = 16
            game.ebullets.clear()
            game.add_text("FASE 2", W / 2, 150, WHITE, big=True, life=2.0)
            sfx("armor_break")
            sfx("boss")
            for _ in range(40):
                v = from_angle(random.uniform(0, math.tau)) * random.uniform(100, 420)
                game.particles.append({"p": Vector2(self.pos), "v": v, "life": random.uniform(0.4, 0.8), "max": 0.8,
                                       "r": random.uniform(1.5, 3.5), "follow": False})

        if self.phase == 1:
            self.angle += 3.6 * k * dt  # gira rápido
            self.move_timer -= dt
            if self.target is None or self.move_timer <= 0 or self.pos.distance_to(self.target) < 25:
                if random.random() < 0.45:
                    self.target = pl.pos + Vector2(random.uniform(-120, 120), random.uniform(-120, 120))
                else:
                    self.target = Vector2(random.uniform(150, W - 150), random.uniform(150, H - 200))
                self.move_timer = random.uniform(0.6, 1.2)
            d = self.target - self.pos
            if d.length_squared() > 0:
                self.pos += d.normalize() * 310 * k * dt
            self.clamp_arena(game)
            self.fire_t -= dt
            if self.fire_t <= 0:
                self.fire_t = 0.45 / k
                self.shoot_drops(game, [0])
            self.burst_t -= dt
            if self.burst_t <= 0:
                self.burst_t = 4.5 / k
                self.shoot_drops(game, [-0.3, 0.3])
            if self.pos.distance_to(pl.pos) < self.a + pl.r * 0.5:
                game.hurt_player(14, self.pos)
        else:
            self.orbit += (1.0 if self.sub == "rest" else 7.5 * k) * dt
            self.sub_t += dt
            if self.sub == "expand":
                u = clamp(self.sub_t / 0.9, 0, 1)
                self.core_r = self.base_core + (self.base_a - self.base_core) * u
                self.a = self.core_r
                if u >= 1:
                    self.sub, self.sub_t = "aim", 0.0
            elif self.sub == "aim":
                if self.sub_t >= 0.8 / k:
                    d = pl.pos - self.pos
                    d = d.normalize() if d.length_squared() > 0 else Vector2(1, 0)
                    self.vel = d * 680 * k
                    self.sub, self.sub_t, self.bounces = "bounce", 0.0, 0
                    sfx("dash")
            elif self.sub == "bounce":
                self.pos += self.vel * dt
                m = self.a + game.spike_depth + 6
                hit = False
                if self.pos.x < m:
                    self.pos.x, self.vel.x, hit = m, abs(self.vel.x), True
                elif self.pos.x > W - m:
                    self.pos.x, self.vel.x, hit = W - m, -abs(self.vel.x), True
                if self.pos.y < m:
                    self.pos.y, self.vel.y, hit = m, abs(self.vel.y), True
                elif self.pos.y > H - m:
                    self.pos.y, self.vel.y, hit = H - m, -abs(self.vel.y), True
                if hit:
                    self.bounces += 1
                    game.shake = max(game.shake, 7)
                    sfx("hit")
                    for _ in range(10):
                        v = from_angle(random.uniform(0, math.tau)) * random.uniform(60, 260)
                        game.particles.append({"p": Vector2(self.pos), "v": v, "life": 0.4, "max": 0.4, "r": 2,
                                               "follow": False})
                    if self.bounces >= 12:  # para pra recarregar
                        self.sub, self.sub_t, self.vel = "rest", 0.0, Vector2()
            elif self.sub == "rest":
                if self.sub_t >= (2.5 if bl else 4.0):
                    self.sub, self.sub_t = "aim", 0.0
            if self.sub != "bounce":
                self.clamp_arena(game)
            if self.pos.distance_to(pl.pos) < self.a + pl.r * 0.5:
                game.hurt_player(22 if self.sub == "bounce" else 12, self.pos, 450)
            if self.drops_active():
                for c, _ in self.drop_centers():
                    if c.distance_to(pl.pos) < 10 + pl.r:
                        game.hurt_player(10, c)

    def draw(self, surf, t, bl):
        if self.spawn_t > 0:
            return Enemy.draw(self, surf, t, bl)
        active = self.drops_active()
        for c, ang in self.drop_centers():
            n = from_angle(ang)
            tv = Vector2(-n.y, n.x)
            col = ARMOR_RED if active else (110, 0, 0)
            pygame.draw.circle(surf, col, c, 9)
            pygame.draw.polygon(surf, col, [c + n * 21, c + tv * 9, c - tv * 9])
        if self.phase == 1:
            pygame.draw.circle(surf, (255, 170, 170) if self.flash > 0 else ARMOR_RED, self.pos, int(self.a))
            pygame.draw.circle(surf, WHITE, self.pos, int(self.core_r))
        else:
            col = WHITE
            if bl and int(t * 12) % 2 == 0:
                col = (255, 90, 90)
            if self.flash > 0:
                col = (255, 190, 190)
            pygame.draw.circle(surf, col, self.pos, int(self.core_r))
            if self.sub == "rest":
                pulse = 0.5 + 0.5 * math.sin(t * 8)
                pygame.draw.circle(surf, lerp_color((40, 80, 120), (120, 200, 255), pulse), self.pos, int(self.a + 8), 2)
            bw = 110
            r = pygame.Rect(self.pos.x - bw / 2, self.pos.y - self.a - 20, bw, 5)
            pygame.draw.rect(surf, (40, 40, 50), r)
            r.width = int(bw * clamp(self.core / self.core_max, 0, 1))
            pygame.draw.rect(surf, WHITE, r)


class Diamond:
    # losango do boss gêmeos: 3 bordas com escudo e 1 borda aberta (ponto fraco)
    def __init__(self, a, armor, shield_hp, open_edge):
        self.a = a
        self.armor = armor
        self.armor_max = armor
        self.shield_max = shield_hp
        self.shields = [shield_hp] * 4
        self.shields[open_edge] = 0
        self.timers = [0.0] * 4
        self.open = open_edge
        self.pos = Vector2()
        self.angle = 0.0
        self.flash = 0.0
        self.gone = False

    def hit(self, p, dmg):
        d = p - self.pos
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        lx = d.x * ca + d.y * sa
        ly = -d.x * sa + d.y * ca
        if abs(lx) + abs(ly) > self.a:
            return None
        self.flash = 0.08
        k = int((math.atan2(ly, lx) % math.tau) // (math.pi / 2)) % 4
        if k != self.open and self.shields[k] > 0:
            self.shields[k] -= dmg
            if self.shields[k] <= 0:
                self.shields[k] = 0
                self.timers[k] = 5.0
                return "shield_break"
            return "shield_hit"
        self.armor -= dmg
        if self.armor <= 0:
            self.armor = 0
            return "armor_break"
        return "hit"

    def draw(self, surf):
        a = self.a
        ca, sa = math.cos(self.angle), math.sin(self.angle)

        def tw(lx, ly):
            return (self.pos.x + lx * ca - ly * sa, self.pos.y + lx * sa + ly * ca)

        vs = [(a, 0), (0, a), (-a, 0), (0, -a)]
        pygame.draw.polygon(surf, (255, 170, 170) if self.flash > 0 else ARMOR_RED, [tw(*v) for v in vs])
        gap = 8
        for k in range(4):
            if k == self.open:
                continue
            na = math.radians(45 + 90 * k)
            ox, oy = math.cos(na) * gap, math.sin(na) * gap
            v1, v2 = vs[k], vs[(k + 1) % 4]
            p1, p2 = tw(v1[0] + ox, v1[1] + oy), tw(v2[0] + ox, v2[1] + oy)
            if self.shields[k] > 0:
                pygame.draw.line(surf, WHITE, p1, p2, int(2 + 4 * self.shields[k] / self.shield_max))
            else:
                pygame.draw.line(surf, (70, 70, 70), p1, p2, 1)


class TwinBoss(Enemy):
    # Boss 3: dois losangos orbitando um núcleo, persegue o player e solta capangas
    custom_contact = True

    def __init__(self, kind, pos, hp_mult=1.0):
        super().__init__(kind, pos, hp_mult)
        self.orbit = random.uniform(0, math.tau)
        self.dms = [Diamond(44, 120 * hp_mult, 70 * hp_mult, 3) for _ in range(2)]
        self.minion_t = 5.0
        self.minion_n = 0
        self.place_diamonds()
        self.armor = sum(d.armor for d in self.dms)
        self.shield = sum(sum(d.shields) for d in self.dms)

    def place_diamonds(self):
        for i, dm in enumerate(self.dms):
            ang = self.orbit + i * math.pi
            dm.angle = ang
            dm.pos = self.pos + from_angle(ang) * 98

    def break_shield(self):
        for dm in self.dms:
            for i in range(4):
                if i != dm.open and dm.shields[i] > 0:
                    dm.shields[i] = 0
                    dm.timers[i] = 5.0

    def core_exposed(self):
        return all(dm.armor <= 0 for dm in self.dms)

    def hit_core(self, dmg):
        self.core -= dmg
        self.flash = 0.08
        if self.core <= 0:
            self.dead = True
            return "kill"
        return "hit"

    def try_hit(self, p, dmg):
        if self.spawn_t > 0 or self.dead:
            return None
        for dm in self.dms:
            if dm.armor > 0:
                res = dm.hit(p, dmg)
                if res:
                    return res
        if self.core_exposed() and (p - self.pos).length() <= self.core_r + 5:
            return self.hit_core(dmg)
        return None

    def try_area(self, center, radius, dmg):
        best = None
        for dm in self.dms:
            if dm.armor > 0 and dm.pos.distance_to(center) <= radius + dm.a:
                d = center - dm.pos
                dirv = d.normalize() if d.length_squared() > 0 else Vector2(1, 0)
                res = dm.hit(dm.pos + dirv * dm.a * 0.4, dmg)
                best = best or res
        if self.core_exposed() and self.pos.distance_to(center) <= radius + self.core_r:
            best = best or self.hit_core(dmg)
        return best

    def update(self, dt, game):
        if self.spawn_t > 0:
            self.spawn_t -= dt
            self.place_diamonds()
            return
        self.flash = max(0, self.flash - dt)
        bl = game.bloodlust
        k = 1.7 if bl else 1.0
        pl = game.player
        lost = sum(1 for d in self.dms if d.armor <= 0)
        self.orbit += (1.2 + 0.6 * lost) * k * dt
        to_p = pl.pos - self.pos
        if to_p.length_squared() > 0:
            self.pos += to_p.normalize() * 115 * (1 + 0.35 * lost) * k * dt
        m = 70 + game.spike_depth
        self.pos.x = clamp(self.pos.x, m, W - m)
        self.pos.y = clamp(self.pos.y, m, H - m)
        self.place_diamonds()
        for dm in self.dms:
            dm.flash = max(0, dm.flash - dt)
            if dm.armor > 0:
                for i in range(4):
                    if i != dm.open and dm.shields[i] <= 0 and dm.timers[i] > 0:
                        dm.timers[i] -= dt
                        if dm.timers[i] <= 0:
                            dm.shields[i] = dm.shield_max
            elif not dm.gone:
                dm.gone = True
                game.shake = max(game.shake, 12)
                sfx("armor_break")
                for _ in range(30):
                    v = from_angle(random.uniform(0, math.tau)) * random.uniform(100, 380)
                    game.particles.append({"p": Vector2(dm.pos), "v": v, "life": random.uniform(0.3, 0.7), "max": 0.7,
                                           "r": random.uniform(1.5, 3.5), "follow": False})
        self.armor = sum(d.armor for d in self.dms)
        self.shield = sum(sum(d.shields) for d in self.dms if d.armor > 0)

        # capangas
        self.minion_t -= dt
        if self.minion_t <= 0:
            self.minion_t = 3.8 if bl else 6.0
            self.minion_n += 1
            if self.minion_n % 3 == 0:
                game.spawn_minions(self.pos, 1, "gunner")
            else:
                game.spawn_minions(self.pos, 2, "kami")

        # contato
        for dm in self.dms:
            if not dm.gone and dm.pos.distance_to(pl.pos) < dm.a * 0.8 + pl.r:
                game.hurt_player(14, dm.pos)
        if self.pos.distance_to(pl.pos) < self.core_r + pl.r:
            game.hurt_player(14, self.pos)

    def draw(self, surf, t, bl):
        if self.spawn_t > 0:
            return Enemy.draw(self, surf, t, bl)
        for dm in self.dms:
            if not dm.gone:
                pygame.draw.line(surf, (150, 0, 0), self.pos, dm.pos, 6)
        for dm in self.dms:
            if not dm.gone:
                dm.draw(surf)
        col = WHITE
        if bl and int(t * 12) % 2 == 0:
            col = (255, 90, 90)
        if self.flash > 0 and self.core_exposed():
            col = (255, 190, 190)
        pygame.draw.circle(surf, col, self.pos, int(self.core_r))
        if self.core_exposed():
            bw = 90
            r = pygame.Rect(self.pos.x - bw / 2, self.pos.y - self.core_r - 16, bw, 5)
            pygame.draw.rect(surf, (40, 40, 50), r)
            r.width = int(bw * clamp(self.core / self.core_max, 0, 1))
            pygame.draw.rect(surf, WHITE, r)


def make_enemy(kind, pos, hp_mult=1.0):
    cls = {"boss_orb": OrbBoss, "boss_twin": TwinBoss}.get(kind, Enemy)
    return cls(kind, pos, hp_mult)


def make_wave(n):
    """Devolve a lista de tipos de inimigos pra onda n."""
    if n % 10 == 0:
        return [BOSS_ORDER[(n // 10 - 1) % len(BOSS_ORDER)]]
    budget = 2 + n * 1.3
    avail = [k for k, c in ENEMY_TYPES.items() if not c.get("boss") and c["min_wave"] <= n]
    out = []
    while budget > 0 and len(out) < 16:
        cheap = [k for k in avail if ENEMY_TYPES[k]["cost"] <= budget]
        if not cheap:
            break
        k = random.choices(cheap, weights=[1 / ENEMY_TYPES[x]["cost"] for x in cheap])[0]
        out.append(k)
        budget -= ENEMY_TYPES[k]["cost"]
    return out or ["kami"]


# ================================================================= jogador
class Player:
    def __init__(self):
        self.pos = Vector2(W / 2, H / 2)
        self.vel = Vector2()
        self.r = 16
        self.hp = 100.0
        self.energy = 100.0
        self.mods = {k: 0.0 for k in ("dmg", "rate", "speed", "maxhp", "frag", "regen", "bspeed", "dashcost", "dashdist",
                                       "lifesteal", "hpregen", "waveheal")}
        self.perks = []   # até 6
        self.minis = []   # até 12
        self.cur = 0      # arma equipada (0 = pistola)
        self.invuln = 0.0
        self.bullet_inv = 0.0
        self.kb_t = 0.0
        self.dash_t = 0.0
        self.dash_dir = Vector2(1, 0)
        self.stretch, self.stretch_v, self.stretch_ang = 1.0, 0.0, 0.0
        self.shoot_cd = 0.0
        self.special_cd = 0.0
        self.ghost_timer = 0.0

    @property
    def max_hp(self):
        return 100 + self.mods["maxhp"]

    @property
    def dash_cost(self):
        return 18 * (1 - min(0.7, self.mods["dashcost"]))

    @property
    def move_speed(self):
        return 340 * (1 + self.mods["speed"])

    @property
    def dash_time(self):
        return 0.17 * (1 + self.mods["dashdist"])

    def weapon_perks(self):
        return [p for p in self.perks if p["kind"] == "weapon"]

    def weapon(self):
        wp = self.weapon_perks()
        if self.cur <= 0 or self.cur > len(wp):
            return "pistola", 0
        p = wp[self.cur - 1]
        return p["weapon"], p["rarity"]

    def cycle_weapon(self):
        self.cur = (self.cur + 1) % (len(self.weapon_perks()) + 1)

    def recalc(self):
        old_max = self.max_hp
        m = {k: 0.0 for k in self.mods}
        for p in self.perks + self.minis:
            if p["kind"] == "stat":
                m[p["stat"]] += p["value"]
        self.mods = m
        new_max = self.max_hp
        if new_max > old_max:
            self.hp += new_max - old_max
        else:
            self.hp = min(self.hp, new_max)

    def put_perk(self, perk, kind, replace_idx=None):
        lst = self.perks if kind == "main" else self.minis
        if replace_idx is None:
            lst.append(perk)
        else:
            lst[replace_idx] = perk
        self.recalc()
        if kind == "main":
            wp = self.weapon_perks()
            if perk["kind"] == "weapon":
                self.cur = 1 + [i for i, p in enumerate(wp) if p is perk][0]
            else:
                self.cur = min(self.cur, len(wp))

    def hurt(self, amount, from_pos=None, knock=350):
        if self.invuln > 0:
            return False
        self.hp -= amount
        self.invuln = 0.7
        if from_pos is not None:
            d = self.pos - from_pos
            if d.length_squared() > 0:
                self.vel = d.normalize() * knock
                self.kb_t = 0.18
        return True


# ================================================================= layout dos menus de perk
def main_slot(i):
    return (W // 2 + int((i - 2.5) * 46), H - 60)


def mini_slot(i):
    return (W // 2 + int((i - 5.5) * 22), H - 30)


def card_rects(n):
    w, h, gap = 300, 270, 40
    x0 = (W - (n * w + (n - 1) * gap)) // 2
    return [pygame.Rect(x0 + i * (w + gap), 170, w, h) for i in range(n)]


SKIP_RECT = pygame.Rect(W // 2 - 90, 500, 180, 44)


def menu_slots(kind):
    if kind == "main":
        return [(W // 2 + int((i - 2.5) * 90), 430) for i in range(6)], 30
    return [(W // 2 + int((i - 5.5) * 64), 430) for i in range(12)], 22


def draw_card(surf, rect, perk, hovered, t):
    col = RARITIES[perk["rarity"]][1]
    r = rect.inflate(14, 14) if hovered else rect
    pygame.draw.rect(surf, (14, 14, 20), r, border_radius=10)
    pygame.draw.rect(surf, col if perk["rarity"] != 8 else (150, 80, 230), r, 3 if hovered else 2, border_radius=10)
    draw_center(surf, RARITIES[perk["rarity"]][0].upper(), font_b, col if perk["rarity"] != 8 else (150, 80, 230),
                (r.centerx, r.y + 24))
    if perk.get("boss_drop"):
        draw_center(surf, "DROP DO BOSS", font, WHITE, (r.centerx, r.y + 44))
    draw_perk_circle(surf, (r.centerx, r.y + 85), 28, perk, t)
    draw_center(surf, perk["name"], font_m, WHITE, (r.centerx, r.y + 145))
    y = r.y + 182
    for line in wrap_text(perk["text"], font, r.width - 40):
        draw_center(surf, line, font, (210, 210, 220), (r.centerx, y))
        y += 22
    if perk.get("desc"):
        for line in wrap_text(perk["desc"], font, r.width - 40):
            draw_center(surf, line, font, (130, 130, 145), (r.centerx, y + 4))
            y += 20


def draw_tooltip(surf, perk, anchor):
    col = RARITIES[perk["rarity"]][1]
    if perk["rarity"] == 8:
        col = (150, 80, 230)
    l1 = font_b.render(f"{perk['name']} - {RARITIES[perk['rarity']][0]}", True, col)
    l2 = font.render(perk["text"], True, WHITE)
    w = max(l1.get_width(), l2.get_width()) + 20
    box = pygame.Rect(0, 0, w, 52)
    box.midbottom = (anchor[0], anchor[1] - 22)
    box.clamp_ip(pygame.Rect(0, 0, W, H))
    pygame.draw.rect(surf, (20, 20, 28), box, border_radius=6)
    pygame.draw.rect(surf, col, box, 1, border_radius=6)
    surf.blit(l1, (box.x + 10, box.y + 6))
    surf.blit(l2, (box.x + 10, box.y + 28))


def draw_button(surf, rect, label, hovered):
    pygame.draw.rect(surf, (28, 28, 38) if hovered else (16, 16, 22), rect, border_radius=8)
    pygame.draw.rect(surf, WHITE if hovered else (90, 90, 105), rect, 2, border_radius=8)
    draw_center(surf, label, font_m, WHITE if hovered else (190, 190, 200), rect.center)


# ================================================================= jogo
class Game:
    def __init__(self):
        self.reset()

    def reset(self):
        self.t = 0.0
        self.player = Player()
        self.enemies = []
        self.bullets = []
        self.ebullets = []
        self.fragments = []
        self.particles = []
        self.ghosts = []
        self.pulses = []
        self.beams = []
        self.rockets = []
        self.blasts = []
        self.dmg_total = 0.0
        self.dmg_timer = 0.0
        self.dmg_pop = 0.0
        self.dmg_numbers = []
        self.ambient = [{"p": Vector2(random.uniform(0, W), random.uniform(0, H)),
                         "v": Vector2(random.uniform(-8, 8), random.uniform(-14, -4)),
                         "r": random.choice((1, 1, 2)), "ph": random.uniform(0, math.tau)} for _ in range(AMBIENT)]
        self.texts = []
        self.wave = 0
        self.state = "play"   # play | clear | perk | transition | over
        self.clear_t = 0.0
        self.bloodlust = False
        self.bl = 0.0
        self.from_bl = False
        self.time_left = ROOM_TIME
        self.shake = 0.0
        self.flash = 0.0
        self.iris = {"phase": "open", "t": 0.0}
        self.menu = None
        self.start_wave()

    # ---------------------------------------------------------- ondas
    @property
    def spike_depth(self):
        return SPIKE_BASE + (SPIKE_BL - SPIKE_BASE) * self.bl

    def add_text(self, txt, x, y, color=WHITE, big=False, life=2.0):
        self.texts.append({"t": txt, "p": Vector2(x, y), "life": life, "max": life, "c": color, "big": big})

    def spawn_pos(self, margin=100):
        for _ in range(60):
            p = Vector2(random.uniform(margin, W - margin), random.uniform(margin, H - margin - 90))
            if p.distance_to(self.player.pos) > 300:
                return p
        return Vector2(margin, margin)

    def start_wave(self):
        self.wave += 1
        self.bullets.clear()
        self.ebullets.clear()
        self.enemies.clear()
        self.bloodlust = False
        self.is_boss = self.wave % 10 == 0
        self.time_left = BOSS_TIME if self.is_boss else ROOM_TIME
        hp_mult = 1 + 0.06 * (self.wave - 1)
        for kind in make_wave(self.wave):
            self.enemies.append(make_enemy(kind, self.spawn_pos(250 if ENEMY_TYPES[kind].get("boss") else 120), hp_mult))
        if self.is_boss:
            self.enemies[0].pos = Vector2(W / 2, 220)
            self.add_text("BOSS: " + BOSS_NAMES[self.enemies[0].kind], W / 2, 150, (255, 0, 0), big=True, life=2.5)
            sfx("boss")
        else:
            self.add_text(f"ONDA {self.wave}", W / 2, 150, WHITE, big=True, life=1.8)
        self.state = "play"

    def spawn_minions(self, pos, n, kind="kami"):
        for _ in range(n):
            e = Enemy(kind, pos + Vector2(random.uniform(-40, 40), random.uniform(-40, 40)), 1 + 0.06 * (self.wave - 1))
            e.spawn_t = 0.4
            self.enemies.append(e)

    def begin_transition(self):
        self.state = "transition"
        self.iris = {"phase": "close", "t": 0.0}
        sfx("whoosh")

    # ---------------------------------------------------------- perks
    def open_menu(self, kind):
        pl = self.player
        mini = kind == "mini"
        opts = [roll_perk(mini=mini, bonus=0.0 if mini else 0.6) for _ in range(3)]
        if not mini and random.random() < 0.6:  # drop de arma exclusiva do boss
            opts[random.randrange(3)] = roll_perk(bonus=0.6, boss_weapon=True)
        self.menu = {"kind": kind, "step": "choose", "chosen": None, "options": opts}
        self.state = "perk"
        sfx("perk")
        pl.vel = Vector2()

    def close_menu(self):
        self.menu = None
        self.begin_transition()

    def menu_click(self, pos):
        m, pl = self.menu, self.player
        kind = m["kind"]
        lst = pl.perks if kind == "main" else pl.minis
        cap = 6 if kind == "main" else 12
        if m["step"] == "choose":
            for i, r in enumerate(card_rects(len(m["options"]))):
                if r.collidepoint(pos):
                    perk = m["options"][i]
                    sfx("pickup")
                    if len(lst) < cap:
                        pl.put_perk(perk, kind)
                        self.close_menu()
                    else:
                        m["step"], m["chosen"] = "replace", perk
                    return
            if SKIP_RECT.collidepoint(pos):
                sfx("menu")
                self.close_menu()
        else:
            slots, rad = menu_slots(kind)
            for i, c in enumerate(slots[:len(lst)]):
                if Vector2(pos).distance_to(c) <= rad + 4:
                    pl.put_perk(m["chosen"], kind, replace_idx=i)
                    sfx("pickup")
                    self.close_menu()
                    return
            if SKIP_RECT.collidepoint(pos):
                sfx("menu")
                m["step"] = "choose"

    # ---------------------------------------------------------- ações do jogador
    def try_dash(self, keys, mouse):
        pl = self.player
        if self.state not in ("play", "clear") or pl.dash_t > 0 or pl.energy < pl.dash_cost:
            return
        inp = Vector2(keys[pygame.K_d] - keys[pygame.K_a], keys[pygame.K_s] - keys[pygame.K_w])
        if inp.length_squared() == 0:
            inp = Vector2(mouse) - pl.pos
        if inp.length_squared() == 0:
            return
        pl.dash_dir = inp.normalize()
        pl.energy -= pl.dash_cost
        pl.dash_t = pl.dash_time
        pl.bullet_inv = pl.dash_time + 0.15
        pl.stretch, pl.stretch_v = 1.9, 0.0
        pl.stretch_ang = math.atan2(pl.dash_dir.y, pl.dash_dir.x)
        sfx("dash")
        # explosão de pontinhos no ponto de partida
        for _ in range(30):
            v = from_angle(random.uniform(0, math.tau)) * random.uniform(80, 460)
            self.particles.append({"p": Vector2(pl.pos), "v": v, "life": random.uniform(0.35, 0.7), "max": 0.7,
                                   "r": random.uniform(1.2, 2.8), "follow": False})
        # alguns pontinhos seguem o player
        for _ in range(10):
            v = from_angle(random.uniform(0, math.tau)) * random.uniform(60, 200)
            self.particles.append({"p": Vector2(pl.pos), "v": v, "life": random.uniform(0.5, 0.8), "max": 0.8,
                                   "r": random.uniform(1.2, 2.5), "follow": True})

    def try_special(self):
        pl = self.player
        if self.state not in ("play", "clear") or pl.special_cd > 0 or pl.energy < 35:
            return
        pl.energy -= 35
        pl.special_cd = 0.8
        self.pulses.append({"p": Vector2(pl.pos), "r": pl.r, "hit": set()})
        sfx("pulse")

    def spawn_fragment(self, pos):
        self.fragments.append({"p": Vector2(pos) + Vector2(random.uniform(-15, 15), random.uniform(-15, 15)),
                               "v": Vector2(random.uniform(-80, 80), random.uniform(-80, 80)), "t": 12.0})

    def hurt_player(self, amount, from_pos=None, knock=350):
        if self.player.hurt(amount, from_pos, knock):
            sfx("hurt")
            self.shake = max(self.shake, 11)
            for _ in range(10):
                v = from_angle(random.uniform(0, math.tau)) * random.uniform(80, 300)
                self.particles.append({"p": Vector2(self.player.pos), "v": v, "life": 0.4, "max": 0.4, "r": 2.5,
                                       "follow": False, "col": (255, 60, 60)})

    # ---------------------------------------------------------- combate: dano, explosões, raios
    def burst(self, pos, n, speed=(80, 300), life=(0.3, 0.6), r=(1.5, 3.2), col=(255, 255, 255)):
        for _ in range(n):
            v = from_angle(random.uniform(0, math.tau)) * random.uniform(*speed)
            self.particles.append({"p": Vector2(pos), "v": v, "life": random.uniform(*life), "max": life[1],
                                   "r": random.uniform(*r), "follow": False, "col": col})

    def on_hit(self, e, res, dmg, pos):
        pl = self.player
        sfx({"shield_hit": "shield_hit", "shield_break": "shield_break",
             "armor_break": "armor_break", "kill": "kill"}.get(res, "hit"))
        if res in ("shield_hit", "shield_break"):
            self.burst(pos, 5 if res == "shield_hit" else 14, (80, 280), (0.15, 0.35), (1.2, 2.4), (200, 225, 255))
        elif res == "kill":
            self.burst(pos, 12, (100, 380), (0.3, 0.6), (1.5, 3.2))
        else:
            self.burst(pos, 4 if res == "hit" else 14, (80, 280), (0.15, 0.4), (1.2, 2.6), (255, 50, 50))
            self.burst(pos, 2, (60, 200), (0.15, 0.3), (1.2, 2.0))
        # contador de dano + número flutuante
        self.dmg_total += dmg
        self.dmg_timer = 2.5
        self.dmg_pop = 1.0
        if len(self.dmg_numbers) < 60:
            ncol = (170, 170, 185) if res in ("shield_hit", "shield_break") else (255, 210, 60) if res == "kill" else WHITE
            self.dmg_numbers.append({"p": Vector2(pos) + Vector2(random.uniform(-10, 10), random.uniform(-14, 0)),
                                     "v": Vector2(random.uniform(-40, 40), -90), "life": 0.8, "max": 0.8,
                                     "txt": str(max(1, round(dmg))), "col": ncol, "big": res == "kill"})
        if random.random() < 0.10 + pl.mods["frag"]:
            self.spawn_fragment(e.pos)
        if pl.mods["lifesteal"] > 0 and res not in ("shield_hit", "shield_break"):
            pl.hp = min(pl.max_hp, pl.hp + dmg * pl.mods["lifesteal"])
        if res == "shield_break":
            self.shake = max(self.shake, 4)

    def explode(self, p, radius, dmg):
        sfx("boom")
        self.shake = max(self.shake, 9)
        self.blasts.append({"p": Vector2(p), "r": radius, "t": 0.0})
        for _ in range(26):
            v = from_angle(random.uniform(0, math.tau)) * random.uniform(100, 450)
            self.particles.append({"p": Vector2(p), "v": v, "life": random.uniform(0.3, 0.6), "max": 0.6,
                                   "r": random.uniform(1.5, 3.2), "follow": False})
        for e in list(self.enemies):
            if e.spawn_t > 0 or e.dead:
                continue
            res = e.try_area(p, radius, dmg)
            if res:
                self.on_hit(e, res, dmg, p)

    def fire_beam(self, origin, d, dmg, width):
        length = 1500
        perp = Vector2(-d.y, d.x)
        pts = []
        for i in range(31):
            j = 0 if i in (0, 30) else random.uniform(-7, 7)
            pts.append(origin + d * (length * i / 30) + perp * j)
        self.beams.append({"pts": pts, "life": 0.2, "max": 0.2, "w": width})
        sfx("zap")
        self.shake = max(self.shake, 3)
        for e in self.enemies:
            if e.spawn_t > 0 or e.dead:
                continue
            t = clamp((e.pos - origin).dot(d), 0, length)
            if (origin + d * t).distance_to(e.pos) > e.a + width:
                continue
            res, hitp = None, None
            for off in (0, -width * 0.5, width * 0.5):
                for s in range(0, length, 16):
                    q = origin + d * s + perp * off
                    res = e.try_hit(q, dmg)
                    if res:
                        hitp = q
                        break
                if res:
                    break
            if res:
                self.on_hit(e, res, dmg, hitp)

    # ---------------------------------------------------------- eventos
    def handle_event(self, ev, keys, mouse):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_SPACE:
                self.try_dash(keys, mouse)
            elif ev.key == pygame.K_q and self.state in ("play", "clear"):
                self.player.cycle_weapon()
                sfx("menu")
            elif ev.key == pygame.K_r and self.state == "over":
                self.reset()
            elif ev.key == pygame.K_F1 and self.state == "play" and not self.bloodlust:
                self.time_left = 0
            elif ev.key == pygame.K_F2 and self.state == "play":
                for e in self.enemies:
                    e.armor, e.core, e.dead = 0, 0, True
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 3:
                self.try_special()
            elif ev.button == 1 and self.state == "perk" and self.menu:
                self.menu_click(mouse)
        elif ev.type == pygame.MOUSEWHEEL and self.state in ("play", "clear"):
            self.player.cycle_weapon()

    # ---------------------------------------------------------- update
    def update(self, dt, keys, mouse, buttons):
        self.t += dt
        self.shake = max(0.0, self.shake - 45 * dt)
        self.flash = max(0.0, self.flash - 1.8 * dt)
        target = 1.0 if self.bloodlust else 0.0
        self.bl += clamp(target - self.bl, -1.5 * dt, 1.5 * dt)

        # textos, partículas, fantasmas
        for tx in self.texts:
            tx["life"] -= dt
            tx["p"].y -= 14 * dt
        self.texts = [tx for tx in self.texts if tx["life"] > 0]
        pl = self.player
        for p in self.particles:
            p["life"] -= dt
            p["p"] += p["v"] * dt
            if p.get("follow"):
                d = pl.pos - p["p"]
                if d.length_squared() > 1:
                    p["v"] += d.normalize() * 2600 * dt
                p["v"] *= 0.9
            elif not p.get("float"):
                p["v"] *= 0.92
        self.particles = [p for p in self.particles if p["life"] > 0]
        for g in self.ghosts:
            g["life"] -= dt
        self.ghosts = [g for g in self.ghosts if g["life"] > 0]
        for bm in self.beams:
            bm["life"] -= dt
        self.beams = [bm for bm in self.beams if bm["life"] > 0]
        for bs in self.blasts:
            bs["t"] += dt
        self.blasts = [bs for bs in self.blasts if bs["t"] < 0.3]
        for dn in self.dmg_numbers:
            dn["life"] -= dt
            dn["p"] += dn["v"] * dt
            dn["v"] *= 0.96
        self.dmg_numbers = [dn for dn in self.dmg_numbers if dn["life"] > 0]
        self.dmg_pop = max(0.0, self.dmg_pop - 6 * dt)
        for am in self.ambient:
            am["p"] += am["v"] * dt
            if am["p"].y < -4:
                am["p"].update(random.uniform(0, W), H + 4)
            if am["p"].x < -4:
                am["p"].x = W + 4
            elif am["p"].x > W + 4:
                am["p"].x = -4
        if self.bl > 0.3 and random.random() < 0.6:  # brasas subindo na sede de sangue
            self.particles.append({"p": Vector2(random.uniform(0, W), H - 10),
                                   "v": Vector2(random.uniform(-20, 20), -random.uniform(80, 200)),
                                   "life": 1.2, "max": 1.2, "r": random.uniform(1.5, 3), "follow": False,
                                   "col": (255, 60, 40), "float": True})

        # transição entre salas (íris)
        if self.iris:
            self.iris["t"] += dt
            if self.iris["phase"] == "close" and self.iris["t"] >= 0.55:
                self.start_wave()
                self.iris = {"phase": "open", "t": 0.0}
                if self.from_bl:
                    self.flash = 1.0
                    self.from_bl = False
            elif self.iris["phase"] == "open" and self.iris["t"] >= 0.6:
                self.iris = None

        if self.state in ("perk", "over", "transition"):
            return

        # ---------- timer da sala / sede de sangue
        if self.state == "play" and not self.bloodlust:
            self.time_left -= dt
            if self.time_left <= 0:
                self.time_left = 0
                self.bloodlust = True
                self.shake = 14
                sfx("bloodlust")
                self.add_text("SEDE DE SANGUE", W / 2, 150, (255, 30, 30), big=True, life=2.5)

        # ---------- timers do player
        pl.invuln = max(0, pl.invuln - dt)
        pl.bullet_inv = max(0, pl.bullet_inv - dt)
        pl.shoot_cd = max(0, pl.shoot_cd - dt)
        pl.special_cd = max(0, pl.special_cd - dt)
        pl.hp = min(pl.max_hp, pl.hp + pl.mods["hpregen"] * dt)
        if self.dmg_timer > 0:
            self.dmg_timer -= dt
            if self.dmg_timer <= 0:
                self.dmg_total = 0.0

        # ---------- movimento
        inp = Vector2(keys[pygame.K_d] - keys[pygame.K_a], keys[pygame.K_s] - keys[pygame.K_w])
        moving = inp.length_squared() > 0
        if moving:
            inp = inp.normalize()
        if pl.dash_t > 0:
            pl.dash_t -= dt
            pl.pos += pl.dash_dir * 1700 * dt
            pl.ghost_timer -= dt
            if pl.ghost_timer <= 0:
                pl.ghost_timer = 0.018
                self.ghosts.append({"p": Vector2(pl.pos), "ang": pl.stretch_ang, "s": pl.stretch, "life": 0.28, "max": 0.28})
            if pl.dash_t <= 0:
                pl.vel = pl.dash_dir * pl.move_speed * 0.7
        elif pl.kb_t > 0:
            pl.kb_t -= dt
            pl.pos += pl.vel * dt
            pl.vel *= 0.9
        else:
            tgt = inp * pl.move_speed
            diff = tgt - pl.vel
            step = 3800 * dt
            if diff.length() <= step:
                pl.vel = tgt
            else:
                pl.vel += diff.normalize() * step
            pl.pos += pl.vel * dt
        pl.pos.x = clamp(pl.pos.x, pl.r, W - pl.r)
        pl.pos.y = clamp(pl.pos.y, pl.r, H - pl.r)
        if pl.dash_t <= 0 and pl.vel.length() > 120 and random.random() < 0.4:
            self.particles.append({"p": pl.pos + Vector2(random.uniform(-6, 6), random.uniform(-6, 6)),
                                   "v": -pl.vel * 0.08, "life": 0.35, "max": 0.35, "r": 1.5, "follow": False,
                                   "col": (150, 150, 165)})

        # squash & stretch (mola)
        pl.stretch_v += (1 - pl.stretch) * 380 * dt
        pl.stretch_v *= max(0.0, 1 - 9 * dt)
        pl.stretch += pl.stretch_v * dt
        pl.stretch = clamp(pl.stretch, 0.55, 2.1)

        # energia só recarrega parado
        if not moving and pl.dash_t <= 0 and pl.vel.length() < 40:
            pl.energy = min(100, pl.energy + 22 * (1 + pl.mods["regen"]) * dt)

        # espinhos
        edge = min(pl.pos.x, W - pl.pos.x, pl.pos.y, H - pl.pos.y) - pl.r
        if edge < self.spike_depth * 0.75:
            center = Vector2(W / 2, H / 2)
            self.hurt_player(12, from_pos=pl.pos + (pl.pos - center), knock=480)

        # ---------- tiro
        aim = Vector2(mouse) - pl.pos
        aim_dir = aim.normalize() if aim.length_squared() > 0 else Vector2(1, 0)
        wkey, wr = pl.weapon()
        wpn = WEAPONS[wkey]
        if buttons[0] and pl.shoot_cd <= 0:
            pl.shoot_cd = wpn["cd"] / (1 + pl.mods["rate"])
            hand = pl.pos + aim_dir * (pl.r + 14)
            base_ang = math.atan2(aim_dir.y, aim_dir.x)
            dmg = wpn["dmg"] * (1 + pl.mods["dmg"]) * (1 + 0.12 * wr)
            wtype = wpn.get("type", "bullet")
            if wtype == "beam":
                self.fire_beam(hand, aim_dir, dmg, wpn["width"])
            elif wtype == "rocket":
                self.rockets.append({"p": Vector2(hand), "v": aim_dir * 300, "spd": 300.0, "max": wpn["max"],
                                     "turn": wpn["turn"], "life": wpn["life"], "dmg": dmg,
                                     "radius": wpn["radius"], "dead": False})
            else:
                n = wpn["pellets"]
                perp = Vector2(-aim_dir.y, aim_dir.x)
                for i in range(n):
                    lat = 0.0
                    if wpn["mode"] == "fan" and n > 1:
                        off = -wpn["spread"] / 2 + wpn["spread"] * i / (n - 1)
                    elif wpn["mode"] == "par":
                        off = random.uniform(-wpn["spread"] / 2, wpn["spread"] / 2)
                        lat = (i - (n - 1) / 2) * wpn.get("gap", 14)
                    else:
                        off = random.uniform(-wpn["spread"] / 2, wpn["spread"] / 2)
                    sp = wpn["speed"] * (1 + pl.mods["bspeed"]) * (random.uniform(0.9, 1.1) if n > 3 else 1.0)
                    self.bullets.append({"p": hand + perp * lat, "v": from_angle(base_ang + off) * sp,
                                         "life": wpn["life"], "dmg": dmg, "pierce": wpn["pierce"],
                                         "bounce": wpn["bounce"], "hit": set(), "size": wpn.get("size", 4),
                                         "line": wpn.get("line", False)})
            sfx(wpn["snd"])
            for _ in range(2):
                v = from_angle(base_ang + random.uniform(-0.4, 0.4)) * random.uniform(100, 260)
                self.particles.append({"p": Vector2(hand), "v": v, "life": 0.15, "max": 0.15, "r": 1.6, "follow": False})

        # ---------- tiros do player
        for b in self.bullets:
            b["p"] += b["v"] * dt
            b["life"] -= dt
            if b["bounce"] > 0:
                if b["p"].x < 0 or b["p"].x > W:
                    b["v"].x *= -1
                    b["p"].x = clamp(b["p"].x, 0, W)
                    b["bounce"] -= 1
                if b["p"].y < 0 or b["p"].y > H:
                    b["v"].y *= -1
                    b["p"].y = clamp(b["p"].y, 0, H)
                    b["bounce"] -= 1
            pts = [b["p"]]
            if b["size"] >= 8:  # projétil grosso acerta numa área maior
                s = b["size"] * 0.7
                pts += [b["p"] + Vector2(s, 0), b["p"] + Vector2(-s, 0), b["p"] + Vector2(0, s), b["p"] + Vector2(0, -s)]
            for e in self.enemies:
                if id(e) in b["hit"]:
                    continue
                res = None
                for q in pts:
                    res = e.try_hit(q, b["dmg"])
                    if res:
                        break
                if res:
                    self.on_hit(e, res, b["dmg"], b["p"])
                    if b["pierce"] > 0:
                        b["pierce"] -= 1
                        b["hit"].add(id(e))
                    else:
                        b["life"] = 0
                    break
        self.bullets = [b for b in self.bullets if b["life"] > 0 and
                        (b["bounce"] > 0 or (0 < b["p"].x < W and 0 < b["p"].y < H))]

        # ---------- foguetes teleguiados
        for r in self.rockets:
            r["life"] -= dt
            tgt, best = None, 1e9
            for e in self.enemies:
                if e.spawn_t > 0 or e.dead:
                    continue
                dd = e.pos.distance_to(r["p"])
                if dd < best:
                    best, tgt = dd, e
            ang = math.atan2(r["v"].y, r["v"].x)
            if tgt:
                want = math.atan2(tgt.pos.y - r["p"].y, tgt.pos.x - r["p"].x)
                ang += clamp(wrap_angle(want - ang), -r["turn"] * dt, r["turn"] * dt)
            r["spd"] = min(r["max"], r["spd"] + 700 * dt)
            r["v"] = from_angle(ang) * r["spd"]
            r["p"] += r["v"] * dt
            self.particles.append({"p": Vector2(r["p"]), "v": -r["v"] * 0.08, "life": 0.3, "max": 0.3, "r": 2,
                                   "follow": False})
            boom = r["life"] <= 0 or not (0 < r["p"].x < W and 0 < r["p"].y < H)
            if not boom:
                for e in self.enemies:
                    if e.spawn_t <= 0 and r["p"].distance_to(e.pos) < e.a + 6:
                        boom = True
                        break
            if boom:
                r["dead"] = True
                self.explode(r["p"], r["radius"], r["dmg"])
        self.rockets = [r for r in self.rockets if not r["dead"]]

        # ---------- inimigos
        for e in self.enemies:
            e.update(dt, self)
            if e.spawn_t > 0 or e.dead:
                continue
            if e.custom_contact:
                continue
            d = e.pos.distance_to(pl.pos)
            if e.kamikaze:
                if d < e.a + pl.r:
                    self.hurt_player(18, from_pos=e.pos, knock=420)
                    e.dead = True
            elif d < e.a * 0.8 + pl.r:
                self.hurt_player(12, from_pos=e.pos)
        if any(e.boss and e.dead for e in self.enemies):  # boss morreu: capangas explodem junto
            for e in self.enemies:
                e.dead = True
            self.ebullets.clear()
        for e in self.enemies:
            if e.dead:
                sfx("kill")
                self.shake = max(self.shake, 5 + e.a * 0.12)
                for _ in range(int(14 + e.a * 0.6)):
                    v = from_angle(random.uniform(0, math.tau)) * random.uniform(80, 380)
                    self.particles.append({"p": Vector2(e.pos), "v": v, "life": random.uniform(0.3, 0.7), "max": 0.7,
                                           "r": random.uniform(1.5, 3.5), "follow": False,
                                           "col": random.choice([(255, 0, 0), (255, 255, 255), (255, 120, 120)])})
                self.blasts.append({"p": Vector2(e.pos), "r": e.a * 2.2, "t": 0.0})
                if random.random() < 0.4:
                    self.spawn_fragment(e.pos)
        self.enemies = [e for e in self.enemies if not e.dead]

        # ---------- tiros inimigos
        for b in self.ebullets:
            b["p"] += b["v"] * dt
            if pl.bullet_inv <= 0 and b["p"].distance_to(pl.pos) < pl.r + 5:
                self.hurt_player(10, from_pos=b["p"], knock=220)
                if pl.invuln > 0.6:
                    b["p"].update(-999, -999)
        self.ebullets = [b for b in self.ebullets if -20 < b["p"].x < W + 20 and -20 < b["p"].y < H + 20]

        # ---------- pulso
        for pu in self.pulses:
            pu["r"] += 560 * dt
            for b in self.ebullets:
                if b["p"].distance_to(pu["p"]) < pu["r"] + 8:
                    b["p"].update(-999, -999)
            for i, e in enumerate(self.enemies):
                if i not in pu["hit"] and e.pos.distance_to(pu["p"]) < pu["r"] + e.a:
                    pu["hit"].add(i)
                    if e.shield > 0 and e.armor > 0:
                        e.break_shield()
                        sfx("shield_break")
        self.pulses = [p for p in self.pulses if p["r"] < 300]

        # ---------- fragmentos de energia
        for f in self.fragments:
            f["t"] -= dt
            f["p"] += f["v"] * dt
            f["v"] *= 0.95
            d = pl.pos - f["p"]
            if 0 < d.length() < 120:
                f["p"] += d.normalize() * 300 * dt
            if d.length() < pl.r + 8:
                pl.energy = min(100, pl.energy + 20)
                f["t"] = 0
                sfx("pickup", 0.6)
                self.burst(f["p"], 8, (60, 220), (0.2, 0.4), (1.5, 2.5), BLUE)
        self.fragments = [f for f in self.fragments if f["t"] > 0]

        # ---------- morreu?
        if pl.hp <= 0:
            pl.hp = 0
            self.state = "over"
            return

        # ---------- onda limpa
        if self.state == "play" and not self.enemies:
            self.state = "clear"
            self.clear_t = 1.3
            pl.energy = min(100, pl.energy + 40)
            heal = 10 + pl.mods["waveheal"]
            pl.hp = min(pl.max_hp, pl.hp + heal)
            self.add_text(f"+{heal:.0f} vida", pl.pos.x, pl.pos.y - 40, (235, 80, 90), life=1.5)
            if self.bloodlust:
                self.bloodlust = False
                self.from_bl = True
            self.add_text("ONDA LIMPA", W / 2, 150, WHITE, big=True, life=1.5)
        elif self.state == "clear":
            self.clear_t -= dt
            if self.clear_t <= 0:
                if self.wave % 10 == 0:
                    self.open_menu("main")
                elif self.wave % 5 == 0:
                    self.open_menu("mini")
                else:
                    self.begin_transition()

    # ---------------------------------------------------------- desenho
    def draw_spikes(self):
        spike_layer.fill((0, 0, 0, 0))
        step = 28
        depth = self.spike_depth
        bl = self.bl
        for idx, x in enumerate(range(0, W, step)):
            a = int(clamp(85 + 55 * math.sin(self.t * 3 + idx * 0.45) + bl * 90, 0, 255))
            d = depth * (1 + 0.12 * math.sin(self.t * 4 + idx * 0.45))
            col = (255, 0, 0, a)
            pygame.draw.polygon(spike_layer, col, [(x, 0), (x + step, 0), (x + step / 2, d)])
            pygame.draw.polygon(spike_layer, col, [(x, H), (x + step, H), (x + step / 2, H - d)])
        for idx, y in enumerate(range(0, H, step)):
            a = int(clamp(85 + 55 * math.sin(self.t * 3 + idx * 0.45 + 2) + bl * 90, 0, 255))
            d = depth * (1 + 0.12 * math.sin(self.t * 4 + idx * 0.45 + 2))
            col = (255, 0, 0, a)
            pygame.draw.polygon(spike_layer, col, [(0, y), (0, y + step), (d, y + step / 2)])
            pygame.draw.polygon(spike_layer, col, [(W, y), (W, y + step), (W - d, y + step / 2)])
        if bl > 0.01:  # borda vermelha viva
            pulse = 0.65 + 0.35 * math.sin(self.t * 6)
            for i in range(7):
                a = int(bl * pulse * (200 - i * 26))
                if a > 0:
                    pygame.draw.rect(spike_layer, (255, 0, 0, a), (i * 3, i * 3, W - i * 6, H - i * 6), 3)
        screen.blit(spike_layer, (0, 0))

    def draw_player(self, surf, mouse):
        pl = self.player
        if pl.invuln > 0 and int(pl.invuln * 20) % 2 == 0:
            return
        s = pl.stretch
        pygame.draw.polygon(surf, WHITE, ellipse_points(pl.pos.x, pl.pos.y, pl.r * s, pl.r / s, pl.stretch_ang))
        if pl.mods["lifesteal"] > 0:  # presas de vampiro, viradas pro mouse (uma de cada lado da mão)
            av = Vector2(mouse) - pl.pos
            base_ang = math.atan2(av.y, av.x) if av.length_squared() > 0 else 0.0
            for side in (-0.5, 0.5):
                n = from_angle(base_ang + side)
                tv = Vector2(-n.y, n.x)
                root = pl.pos + n * (pl.r - 4)
                fang = [root + tv * 4, root - tv * 4, pl.pos + n * (pl.r + 9)]
                pygame.draw.polygon(surf, WHITE, fang)
                pygame.draw.polygon(surf, (200, 0, 0), fang, 1)
        aim = Vector2(mouse) - pl.pos
        aim_dir = aim.normalize() if aim.length_squared() > 0 else Vector2(1, 0)
        pygame.draw.circle(surf, WHITE, pl.pos + aim_dir * (pl.r + 14), 6)

    def draw_hud(self, surf, mouse):
        pl = self.player
        cx = W // 2
        # arma atual
        wkey, wr = pl.weapon()
        wcol = RARITIES[wr][1] if wkey != "pistola" else WHITE
        if wkey != "pistola" and wr == 8:
            wcol = (150, 80, 230)
        surf.blit(font.render(f"{WEAPONS[wkey]['name']}", True, wcol), (cx - 190, H - 136))
        if pl.weapon_perks():
            surf.blit(font.render("[Q] trocar arma", True, (80, 80, 95)), (cx + 90, H - 136))
        # vida
        hb = pygame.Rect(cx - 190, H - 112, 380, 18)
        pygame.draw.rect(surf, (28, 28, 36), hb, border_radius=3)
        fill = hb.copy()
        fill.width = int(hb.width * clamp(pl.hp / pl.max_hp, 0, 1))
        pygame.draw.rect(surf, (235, 80, 90), fill, border_radius=3)
        pygame.draw.rect(surf, (90, 90, 105), hb, 1, border_radius=3)
        # energia (menor e mais fina)
        eb = pygame.Rect(cx - 150, H - 88, 300, 7)
        pygame.draw.rect(surf, (28, 28, 36), eb, border_radius=2)
        fill = eb.copy()
        fill.width = int(eb.width * pl.energy / 100)
        pygame.draw.rect(surf, BLUE, fill, border_radius=2)
        # slots
        hover = None
        for i in range(6):
            c = main_slot(i)
            if i < len(pl.perks):
                draw_perk_circle(surf, c, 14, pl.perks[i], self.t)
                if Vector2(mouse).distance_to(c) < 17:
                    hover = (pl.perks[i], c)
            else:
                pygame.draw.circle(surf, WHITE, c, 14, 2)
        for i in range(12):
            c = mini_slot(i)
            if i < len(pl.minis):
                draw_perk_circle(surf, c, 7, pl.minis[i], self.t)
                if Vector2(mouse).distance_to(c) < 9:
                    hover = (pl.minis[i], c)
            else:
                pygame.draw.circle(surf, (200, 200, 200), c, 7, 1)
        if hover:
            draw_tooltip(surf, hover[0], hover[1])

        # timer
        mins, secs = divmod(int(self.time_left), 60)
        tcol = WHITE
        if self.bloodlust:
            tcol = (255, 40, 40)
        elif self.time_left < 30 and int(self.t * 3) % 2 == 0:
            tcol = (255, 90, 90)
        draw_center(surf, f"{mins:02d}:{secs:02d}", font_m, tcol, (W // 2, 44))
        if self.bloodlust:
            a = 0.6 + 0.4 * math.sin(self.t * 8)
            draw_center(surf, "SEDE DE SANGUE", font_b, lerp_color((90, 0, 0), (255, 40, 40), a), (W // 2, 72))
        surf.blit(font_b.render(("BOSS  " if self.is_boss else "") + f"Onda {self.wave}", True, WHITE), (SPIKE_BL + 14, SPIKE_BL + 8))
        if self.wave == 1 and self.t < 25:
            hint = "WASD mover  |  ESPAÇO dash  |  esq. atirar  |  dir. pulso  |  parado recarrega energia"
            surf.blit(font.render(hint, True, (80, 80, 95)), (SPIKE_BL + 14, SPIKE_BL + 32))

        # contador de dano acumulado (some se ficar um tempo sem causar dano)
        if self.dmg_total > 0:
            fade = clamp(self.dmg_timer / 0.6, 0, 1)
            tot = self.dmg_total
            col = WHITE if tot < 300 else (255, 210, 60) if tot < 1000 else (255, 80, 80)
            img = pygame.transform.rotozoom(dmg_font.render(str(int(tot)), True, col), 0, 1 + 0.35 * self.dmg_pop)
            img.set_alpha(int(255 * fade))
            rect = img.get_rect(topright=(W - 70, 100))
            lab = font_b.render("DANO", True, (150, 150, 165))
            lab.set_alpha(int(255 * fade))
            surf.blit(lab, lab.get_rect(topright=(W - 70, 78)))
            surf.blit(img, rect)
            bar = pygame.Rect(0, rect.bottom + 4, int(120 * clamp(self.dmg_timer / 2.5, 0, 1)), 3)
            bar.right = W - 70
            pygame.draw.rect(surf, col, bar)

    def draw_perk_menu(self, surf, mouse):
        dim_layer.fill((0, 0, 0, 205))
        surf.blit(dim_layer, (0, 0))
        m, pl = self.menu, self.player
        kind = m["kind"]
        lst = pl.perks if kind == "main" else pl.minis
        if m["step"] == "choose":
            title = "BOSS DERROTADO - escolha um perk" if kind == "main" else "Escolha um mini perk"
            draw_center(surf, title, big_font if kind == "main" else font_m, WHITE, (W // 2, 90 if kind == "main" else 100))
            for r, perk in zip(card_rects(len(m["options"])), m["options"]):
                draw_card(surf, r, perk, r.collidepoint(mouse), self.t)
            cap = 6 if kind == "main" else 12
            if len(lst) >= cap:
                draw_center(surf, "Slots cheios: ao escolher, você vai trocar por um perk que já tem.", font, (200, 200, 120), (W // 2, 470))
            draw_button(surf, SKIP_RECT, "Pular", SKIP_RECT.collidepoint(mouse))
        else:
            draw_center(surf, "Clique no perk que será substituído", font_m, WHITE, (W // 2, 80))
            draw_card(surf, pygame.Rect(W // 2 - 150, 120, 300, 230), m["chosen"], False, self.t)
            slots, rad = menu_slots(kind)
            hover = None
            for i, c in enumerate(slots[:len(lst)]):
                h = Vector2(mouse).distance_to(c) <= rad + 4
                draw_perk_circle(surf, c, rad + (4 if h else 0), lst[i], self.t)
                if h:
                    hover = (lst[i], c)
            if hover:
                draw_tooltip(surf, hover[0], hover[1])
            draw_button(surf, SKIP_RECT, "Voltar", SKIP_RECT.collidepoint(mouse))

    def draw(self, mouse):
        screen.fill(lerp_color((0, 0, 0), BLOODLUST_BG, self.bl))
        self.draw_spikes()

        for f in self.fragments:
            if f["t"] > 3 or int(f["t"] * 8) % 2 == 0:
                pygame.draw.circle(screen, BLUE, f["p"], 6)
                pygame.draw.circle(screen, (200, 230, 255), f["p"], 3)
        for e in self.enemies:
            e.draw(screen, self.t, self.bloodlust)
        for b in self.bullets:
            if b["line"]:
                pygame.draw.line(screen, WHITE, b["p"], b["p"] - b["v"].normalize() * 16, 2)
            else:
                pygame.draw.circle(screen, WHITE, b["p"], b["size"])
        for r in self.rockets:
            n = r["v"].normalize()
            tv = Vector2(-n.y, n.x)
            pygame.draw.polygon(screen, WHITE, [r["p"] + n * 11, r["p"] - n * 8 + tv * 5, r["p"] - n * 8 - tv * 5])
        for b in self.ebullets:
            pygame.draw.circle(screen, (255, 70, 70), b["p"], 5)

        overlay.fill((0, 0, 0, 0))
        for g in self.ghosts:
            a = int(110 * g["life"] / g["max"])
            pygame.draw.polygon(overlay, (220, 235, 255, a), ellipse_points(g["p"].x, g["p"].y, 16 * g["s"], 16 / g["s"], g["ang"]))
        for p in self.particles:
            a = int(255 * clamp(p["life"] / p["max"], 0, 1))
            c = p.get("col", (255, 255, 255))
            pygame.draw.circle(overlay, (c[0], c[1], c[2], a), p["p"], p["r"])
        for pu in self.pulses:
            a = int(255 * clamp(1 - pu["r"] / 300, 0, 1))
            pygame.draw.circle(overlay, (190, 225, 255, a), pu["p"], int(pu["r"]), 4)
        for am in self.ambient:
            a = int(30 + 25 * math.sin(self.t * 1.5 + am["ph"]))
            c = lerp_color((255, 255, 255), (255, 60, 60), self.bl)
            pygame.draw.circle(overlay, (c[0], c[1], c[2], a), am["p"], am["r"])
        for bm in self.beams:
            a = int(255 * bm["life"] / bm["max"])
            pygame.draw.line(overlay, (255, 255, 255, int(a * 0.25)), bm["pts"][0], bm["pts"][-1], int(bm["w"]))
            pygame.draw.lines(overlay, (255, 255, 255, a), False, bm["pts"], 5)
            pygame.draw.lines(overlay, (190, 215, 255, a), False, bm["pts"], 2)
        for bs in self.blasts:
            u = clamp(bs["t"] / 0.3, 0, 1)
            rr = int(bs["r"] * (0.25 + 0.75 * min(1.0, u * 3)))
            a = int(255 * (1 - u))
            pygame.draw.circle(overlay, (255, 255, 255, int(a * 0.25)), bs["p"], rr)
            pygame.draw.circle(overlay, (255, 255, 255, a), bs["p"], rr, 3)
        screen.blit(overlay, (0, 0))

        if self.state != "over":
            self.draw_player(screen, mouse)
        self.draw_hud(screen, mouse)

        for tx in self.texts:
            f = big_font if tx["big"] else font_b
            img = f.render(tx["t"], True, tx["c"])
            img.set_alpha(int(255 * clamp(tx["life"] / (tx["max"] * 0.4), 0, 1)))
            screen.blit(img, img.get_rect(center=(int(tx["p"].x), int(tx["p"].y))))

        for dn in self.dmg_numbers:
            img = (font_m if dn["big"] else font_b).render(dn["txt"], True, dn["col"])
            img.set_alpha(int(255 * clamp(dn["life"] / (dn["max"] * 0.5), 0, 1)))
            screen.blit(img, img.get_rect(center=(int(dn["p"].x), int(dn["p"].y))))

        if self.iris:  # efeito de passagem entre salas
            R = math.hypot(W, H) / 2 + 20
            u = clamp(self.iris["t"] / (0.55 if self.iris["phase"] == "close" else 0.6), 0, 1)
            radius = R * (1 - u) ** 1.5 if self.iris["phase"] == "close" else R * (1 - (1 - u) ** 2)
            if radius < R:
                iris_layer.fill((0, 0, 0, 255))
                if radius > 1:
                    pygame.draw.circle(iris_layer, (0, 0, 0, 0), (int(self.player.pos.x), int(self.player.pos.y)), int(radius))
                screen.blit(iris_layer, (0, 0))

        if self.state == "perk" and self.menu:
            self.draw_perk_menu(screen, mouse)

        if self.state == "over":
            draw_center(screen, "Você morreu", big_font, (255, 40, 40), (W // 2, H // 2 - 30))
            draw_center(screen, f"Chegou até a onda {self.wave}  -  aperte R pra tentar de novo", font_b, WHITE, (W // 2, H // 2 + 25))

        if self.flash > 0:  # flash branco
            dim_layer.fill((255, 255, 255, int(255 * clamp(self.flash, 0, 1))))
            screen.blit(dim_layer, (0, 0))

        if self.state in ("play", "clear"):  # mira
            pygame.draw.circle(screen, WHITE, mouse, 8, 1)
            pygame.draw.circle(screen, WHITE, mouse, 1)


# ================================================================= menu principal / pausa
def menu_items(mode):
    items = [("Jogar", "play") if mode == "menu" else ("Continuar", "resume")]
    sw, sh = SIZES[settings["size"]]
    items.append((f"Tamanho da tela: {sw}x{sh}", "size"))
    items.append((f"Tela cheia: {'Sim' if settings['full'] else 'Não'}", "full"))
    if mode == "pause":
        items.append(("Menu principal", "menu"))
    items.append(("Sair", "quit"))
    return items


def item_rects(n):
    return [pygame.Rect(W // 2 - 230, 270 + i * 72, 460, 56) for i in range(n)]


def draw_menu(mode, mouse, sel, t, game):
    if mode == "pause" and game:
        game.draw(Vector2(-100, -100))
        dim_layer.fill((0, 0, 0, 200))
        screen.blit(dim_layer, (0, 0))
        draw_center(screen, "PAUSADO", title_font, WHITE, (W // 2, 160))
    else:
        screen.fill((0, 0, 0))
        pulse = 0.5 + 0.5 * math.sin(t * 2)
        draw_center(screen, "NEBULOUS-LIKE", title_font, lerp_color((200, 200, 200), (255, 255, 255), pulse), (W // 2, 150))
        pygame.draw.line(screen, lerp_color((90, 0, 0), (255, 0, 0), pulse), (W // 2 - 220, 205), (W // 2 + 220, 205), 2)
    items = menu_items(mode)
    for i, (r, (label, _)) in enumerate(zip(item_rects(len(items)), items)):
        draw_button(screen, r, label, r.collidepoint(mouse) or i == sel)


# ================================================================= loop principal
def main():
    init_audio()
    mode = "menu"  # menu | game | pause
    game = None
    sel = 0
    t = 0.0

    def do_action(act):
        nonlocal mode, game
        sfx("menu")
        if act == "play":
            game = Game()
            mode = "game"
        elif act == "resume":
            mode = "game"
        elif act == "size":
            settings["size"] = (settings["size"] + 1) % len(SIZES)
            apply_display()
        elif act == "full":
            settings["full"] = not settings["full"]
            apply_display()
        elif act == "menu":
            mode, game = "menu", None
        elif act == "quit":
            pygame.quit()
            sys.exit()

    while True:
        dt = min(clock.tick(60) / 1000, 0.05)
        t += dt
        mouse = get_mouse()
        keys = pygame.key.get_pressed()
        buttons = pygame.mouse.get_pressed()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if mode in ("menu", "pause"):
                items = menu_items(mode)
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE and mode == "pause":
                        mode = "game"
                    elif ev.key == pygame.K_UP:
                        sel = (sel - 1) % len(items)
                    elif ev.key == pygame.K_DOWN:
                        sel = (sel + 1) % len(items)
                    elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        do_action(items[sel % len(items)][1])
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    for r, (_, act) in zip(item_rects(len(items)), items):
                        if r.collidepoint(get_mouse()):
                            do_action(act)
                            break
            elif mode == "game":
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    mode, sel = "pause", 0
                else:
                    game.handle_event(ev, keys, mouse)

        if mode == "game":
            game.update(dt, keys, mouse, buttons)
            game.draw(mouse)
            pygame.mouse.set_visible(game.state not in ("play", "clear"))
            present(game.shake)
        else:
            pygame.mouse.set_visible(True)
            draw_menu(mode, mouse, sel, t, game)
            present()


if __name__ == "__main__":
    main()
