"""
Protótipo estilo Nebulous (roguelike top-down, só formas geométricas)

Controles:
  W A S D ........ mover
  ESPAÇO ......... dash (gasta energia)
  Botão esquerdo . atirar (segura pra metralhar)
  Botão direito .. pulso (quebra escudos e apaga tiros inimigos, gasta energia)
  R .............. reiniciar (quando morrer)
  ESC ............ sair

Instalar: pip install pygame
"""
import math
import random
import sys

import pygame
from pygame import Vector2

pygame.init()
W, H = 1280, 720
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Nebulous-like")
clock = pygame.time.Clock()
font = pygame.font.SysFont("arial", 16)
font_b = pygame.font.SysFont("arial", 18, bold=True)
big_font = pygame.font.SysFont("arial", 46, bold=True)
overlay = pygame.Surface((W, H), pygame.SRCALPHA)
pygame.mouse.set_visible(False)

# ----------------------------------------------------------------- cores
BG = (16, 16, 22)
GRID = (24, 24, 32)
WHITE = (245, 245, 245)
RED = (215, 45, 55)
DARK_RED = (95, 22, 30)
GOLD = (255, 200, 40)
BLUE = (80, 170, 255)
SPIKE = 18  # profundidade dos espinhos


# ----------------------------------------------------------------- utilidades
def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def wrap_angle(a):
    return (a + math.pi) % math.tau - math.pi


def from_angle(a):
    return Vector2(math.cos(a), math.sin(a))


def ellipse_points(cx, cy, rx, ry, angle, n=28):
    ca, sa = math.cos(angle), math.sin(angle)
    pts = []
    for i in range(n):
        t = i / n * math.tau
        x, y = math.cos(t) * rx, math.sin(t) * ry
        pts.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return pts


def lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ----------------------------------------------------------------- perks
# (nome, stat, valor base, texto, é porcentagem?)
PERKS = [
    ("Ferro Quente", "dmg", 0.10, "+{}% de dano", True),
    ("Gatilho Leve", "rate", 0.08, "+{}% cadência de tiro", True),
    ("Pés Leves", "speed", 0.05, "+{}% velocidade", True),
    ("Casco Reforçado", "maxhp", 10, "+{} vida máxima", False),
    ("Faísca", "frag", 0.05, "+{}% chance de fragmento", True),
    ("Calmaria", "regen", 0.10, "+{}% recarga de energia", True),
    ("Projétil Veloz", "bspeed", 0.08, "+{}% velocidade do tiro", True),
    ("Dash Eficiente", "dashcost", 0.06, "-{}% custo do dash", True),
]
# (nome, cor, multiplicador, peso no sorteio)
RARITIES = [
    ("Comum", (80, 220, 110), 1.0, 50),
    ("Raro", (80, 160, 255), 1.6, 28),
    ("Épico", (180, 90, 255), 2.4, 14),
    ("Lendário", (255, 200, 40), 3.5, 6),
    ("Mítico", (255, 50, 50), 5.0, 2),
]


def roll_perk():
    r = random.choices(range(len(RARITIES)), weights=[x[3] for x in RARITIES])[0]
    name, stat, base, fmt, pct = random.choice(PERKS)
    value = base * RARITIES[r][2]
    shown = round(value * 100) if pct else round(value)
    return {"name": name, "stat": stat, "value": value, "rarity": r, "text": fmt.format(shown)}


# ----------------------------------------------------------------- inimigo
class Enemy:
    def __init__(self, pos, hp_mult=1.0, boss=False):
        self.pos = Vector2(pos)
        self.boss = boss
        self.a = 80 if boss else 46  # "raio" do losango
        self.angle = random.uniform(-math.pi, math.pi)  # frente = +x local
        k = 4 if boss else 1
        self.armor_max = 80 * hp_mult * k
        self.armor = self.armor_max
        self.shield_max = 120 * hp_mult * (2 if boss else 1)
        self.shield = self.shield_max
        self.shield_timer = 0.0
        self.core_max = 60 * hp_mult * k
        self.core = self.core_max
        self.move_dir = Vector2()
        self.move_timer = random.uniform(0.3, 1.2)
        self.charge = random.uniform(0, 1.0)
        self.charge_time = 2.4 if boss else 3.2
        self.flash = 0.0
        self.dead = False

    @property
    def core_r(self):
        return self.a * 0.28

    def break_shield(self):
        if self.shield > 0:
            self.shield = 0
            self.shield_timer = 5.0
            self.flash = 0.1

    def try_hit(self, p, dmg):
        """Retorna True se o tiro foi 'consumido' (acertou algo)."""
        d = p - self.pos
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        lx = d.x * ca + d.y * sa  # coordenadas locais
        ly = -d.x * sa + d.y * ca
        if self.armor > 0:
            if abs(lx) + abs(ly) > self.a:
                return False
            self.flash = 0.08
            if lx > 0 and self.shield > 0:  # lados da frente = escudo
                self.shield -= dmg
                if self.shield <= 0:
                    self.break_shield()
                return True
            self.armor -= dmg
            if self.armor <= 0:
                self.armor = 0
                self.shield = 0
            return True
        # armadura quebrada: só o núcleo leva dano
        if d.length() <= self.core_r + 4:
            self.core -= dmg
            self.flash = 0.08
            if self.core <= 0:
                self.dead = True
            return True
        return False

    def update(self, dt, game):
        self.flash = max(0, self.flash - dt)

        # regenera escudo
        if self.shield <= 0 and self.armor > 0:
            self.shield_timer -= dt
            if self.shield_timer <= 0:
                self.shield = self.shield_max

        # movimento: só nos eixos (sem diagonal)
        self.move_timer -= dt
        if self.move_timer <= 0:
            self.move_timer = random.uniform(1.0, 2.4)
            to_p = game.player.pos - self.pos
            r = random.random()
            if r < 0.15:
                self.move_dir = Vector2()
            elif r < 0.65:
                if abs(to_p.x) > abs(to_p.y):
                    self.move_dir = Vector2(1 if to_p.x > 0 else -1, 0)
                else:
                    self.move_dir = Vector2(0, 1 if to_p.y > 0 else -1)
            else:
                self.move_dir = random.choice(
                    [Vector2(1, 0), Vector2(-1, 0), Vector2(0, 1), Vector2(0, -1)]
                )
        speed = 45 if self.boss else 60
        self.pos += self.move_dir * speed * dt
        m = self.a + SPIKE + 20
        nx, ny = clamp(self.pos.x, m, W - m), clamp(self.pos.y, m, H - m)
        if (nx, ny) != (self.pos.x, self.pos.y):
            self.pos.update(nx, ny)
            self.move_dir = -self.move_dir

        # rotação lenta apontando o escudo pro player
        to_p = game.player.pos - self.pos
        target = math.atan2(to_p.y, to_p.x)
        diff = wrap_angle(target - self.angle)
        turn = 0.9 * dt
        self.angle += clamp(diff, -turn, turn)

        # triângulos crescem devagar, depois todos atiram
        self.charge += dt
        if self.charge >= self.charge_time:
            self.charge = 0
            self.fire(game)

    def tri_normals(self):
        return [self.angle + math.pi / 4 + k * math.pi / 2 for k in range(4)]

    def fire(self, game):
        spreads = [-0.25, 0, 0.25] if self.boss else [0]
        for ang in self.tri_normals():
            origin = self.pos + from_angle(ang) * (self.a * 0.707 + 16)
            for s in spreads:
                game.enemy_bullets.append(
                    {"p": Vector2(origin), "v": from_angle(ang + s) * 210}
                )

    def draw(self, surf):
        a = self.a
        ca, sa = math.cos(self.angle), math.sin(self.angle)

        def to_world(lx, ly):
            return (self.pos.x + lx * ca - ly * sa, self.pos.y + lx * sa + ly * ca)

        front, right, back, left = to_world(a, 0), to_world(0, a), to_world(-a, 0), to_world(0, -a)
        poly = [front, right, back, left]

        # triângulos (canhões)
        tri_scale = 0.2 + 0.8 * (self.charge / self.charge_time)
        k = a / 46
        for ang in self.tri_normals():
            n = from_angle(ang)
            t = Vector2(-n.y, n.x)
            base = self.pos + n * (a * 0.707 + 4)
            h, w = 22 * tri_scale * k, 10 * tri_scale * k
            pts = [base + n * h, base + t * w, base - t * w]
            col = lerp_color((150, 40, 45), (255, 90, 80), tri_scale)
            pygame.draw.polygon(surf, col, pts)

        # armadura
        if self.armor > 0:
            frac = self.armor / self.armor_max
            col = lerp_color(DARK_RED, RED, frac)
            if self.flash > 0:
                col = (255, 160, 160)
            pygame.draw.polygon(surf, col, poly)
            pygame.draw.polygon(surf, (255, 90, 90), poly, 2)
        else:
            pygame.draw.polygon(surf, (110, 30, 40), poly, 2)

        # escudo dourado nas duas bordas da frente
        if self.armor > 0:
            if self.shield > 0:
                w = 3 + int(4 * self.shield / self.shield_max)
                pygame.draw.lines(surf, GOLD, False, [left, front, right], w)
            else:
                pygame.draw.lines(surf, (100, 85, 30), False, [left, front, right], 1)

        # núcleo
        core_col = (255, 190, 190) if (self.flash > 0 and self.armor <= 0) else WHITE
        pygame.draw.circle(surf, core_col, self.pos, self.core_r)
        if self.armor <= 0:  # barrinha de vida do núcleo
            bw = 50 * (self.a / 46)
            r = pygame.Rect(self.pos.x - bw / 2, self.pos.y - a - 22, bw, 4)
            pygame.draw.rect(surf, (40, 40, 50), r)
            r.width = int(bw * self.core / self.core_max)
            pygame.draw.rect(surf, WHITE, r)


# ----------------------------------------------------------------- jogador
class Player:
    def __init__(self):
        self.pos = Vector2(W / 2, H / 2)
        self.vel = Vector2()
        self.r = 16
        self.hp = 100.0
        self.energy = 100.0
        self.mods = {k: 0.0 for k in ("dmg", "rate", "speed", "maxhp", "frag", "regen", "bspeed", "dashcost")}
        self.perks = []
        self.invuln = 0.0
        self.bullet_inv = 0.0  # i-frames do dash (só contra tiros)
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
        return 20 * (1 - min(0.7, self.mods["dashcost"]))

    @property
    def move_speed(self):
        return 290 * (1 + self.mods["speed"])

    def add_perk(self, perk):
        self.perks.append(perk)
        self.mods[perk["stat"]] += perk["value"]
        if perk["stat"] == "maxhp":
            self.hp += perk["value"]

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


# ----------------------------------------------------------------- jogo
class Game:
    def __init__(self):
        self.spike_surf = self.build_spikes()
        self.reset()

    def build_spikes(self):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        step = 28
        for x in range(0, W, step):
            pygame.draw.polygon(s, RED, [(x, 0), (x + step, 0), (x + step / 2, SPIKE)])
            pygame.draw.polygon(s, RED, [(x, H), (x + step, H), (x + step / 2, H - SPIKE)])
        for y in range(0, H, step):
            pygame.draw.polygon(s, RED, [(0, y), (0, y + step), (SPIKE, y + step / 2)])
            pygame.draw.polygon(s, RED, [(W, y), (W, y + step), (W - SPIKE, y + step / 2)])
        return s

    def reset(self):
        self.player = Player()
        self.enemies = []
        self.bullets = []
        self.enemy_bullets = []
        self.fragments = []
        self.particles = []
        self.ghosts = []
        self.pulses = []
        self.texts = []
        self.room = 0
        self.state = "play"  # play | clear | over
        self.clear_timer = 0.0
        self.next_room()

    # ---------------------------------------------------------- salas
    def next_room(self):
        self.room += 1
        self.bullets.clear()
        self.enemy_bullets.clear()
        idx = (self.room - 1) % 4
        hp_mult = 1 + 0.25 * ((self.room - 1) // 4)
        if idx == 3:
            n, boss = 1, True
            self.add_text("BOSS", W / 2, 140, RED, big=True)
        else:
            n, boss = [1, 2, 3][idx], False
        for _ in range(n):
            while True:
                p = Vector2(random.uniform(150, W - 150), random.uniform(150, H - 220))
                if p.distance_to(self.player.pos) > 300:
                    break
            self.enemies.append(Enemy(p, hp_mult, boss))
        self.state = "play"

    def add_text(self, txt, x, y, color=WHITE, big=False, life=2.0):
        self.texts.append({"t": txt, "p": Vector2(x, y), "life": life, "max": life, "c": color, "big": big})

    # ---------------------------------------------------------- ações
    def try_dash(self, keys, mouse):
        pl = self.player
        if pl.dash_t > 0 or pl.energy < pl.dash_cost or self.state == "over":
            return
        inp = Vector2(keys[pygame.K_d] - keys[pygame.K_a], keys[pygame.K_s] - keys[pygame.K_w])
        if inp.length_squared() == 0:
            inp = Vector2(mouse) - pl.pos
        if inp.length_squared() == 0:
            return
        pl.dash_dir = inp.normalize()
        pl.energy -= pl.dash_cost
        pl.dash_t = 0.16
        pl.bullet_inv = 0.25
        pl.stretch, pl.stretch_v = 1.8, 0.0
        pl.stretch_ang = math.atan2(pl.dash_dir.y, pl.dash_dir.x)
        for _ in range(16):  # explosãozinha de partículas
            v = -pl.dash_dir * random.uniform(60, 260) + Vector2(random.uniform(-90, 90), random.uniform(-90, 90))
            self.particles.append({"p": Vector2(pl.pos), "v": v, "life": 0.4, "max": 0.4, "r": random.uniform(2, 5)})

    def try_special(self, mouse):
        pl = self.player
        if pl.special_cd > 0 or pl.energy < 35 or self.state == "over":
            return
        pl.energy -= 35
        pl.special_cd = 0.8
        self.pulses.append({"p": Vector2(pl.pos), "r": pl.r, "hit": set()})

    def spawn_fragment(self, pos):
        self.fragments.append(
            {"p": Vector2(pos) + Vector2(random.uniform(-15, 15), random.uniform(-15, 15)),
             "v": Vector2(random.uniform(-60, 60), random.uniform(-60, 60)), "t": 12.0}
        )

    # ---------------------------------------------------------- update
    def update(self, dt, keys, mouse, buttons):
        pl = self.player

        # textos e partículas sempre atualizam
        for t in self.texts:
            t["life"] -= dt
            t["p"].y -= 18 * dt
        self.texts = [t for t in self.texts if t["life"] > 0]
        for p in self.particles:
            p["life"] -= dt
            p["p"] += p["v"] * dt
            p["v"] *= 0.93
        self.particles = [p for p in self.particles if p["life"] > 0]
        for g in self.ghosts:
            g["life"] -= dt
        self.ghosts = [g for g in self.ghosts if g["life"] > 0]

        if self.state == "over":
            return

        # --- timers
        pl.invuln = max(0, pl.invuln - dt)
        pl.bullet_inv = max(0, pl.bullet_inv - dt)
        pl.shoot_cd = max(0, pl.shoot_cd - dt)
        pl.special_cd = max(0, pl.special_cd - dt)

        # --- movimento
        inp = Vector2(keys[pygame.K_d] - keys[pygame.K_a], keys[pygame.K_s] - keys[pygame.K_w])
        moving = inp.length_squared() > 0
        if moving:
            inp = inp.normalize()

        if pl.dash_t > 0:
            pl.dash_t -= dt
            pl.pos += pl.dash_dir * 900 * dt
            pl.ghost_timer -= dt
            if pl.ghost_timer <= 0:
                pl.ghost_timer = 0.02
                self.ghosts.append({
                    "p": Vector2(pl.pos), "ang": pl.stretch_ang, "s": pl.stretch, "life": 0.28, "max": 0.28})
            if pl.dash_t <= 0:
                pl.vel = pl.dash_dir * pl.move_speed * 0.6
        elif pl.kb_t > 0:
            pl.kb_t -= dt
            pl.pos += pl.vel * dt
            pl.vel *= 0.9
        else:
            target = inp * pl.move_speed
            diff = target - pl.vel
            step = 2600 * dt
            if diff.length() <= step:
                pl.vel = target
            else:
                pl.vel += diff.normalize() * step
            pl.pos += pl.vel * dt

        pl.pos.x = clamp(pl.pos.x, pl.r, W - pl.r)
        pl.pos.y = clamp(pl.pos.y, pl.r, H - pl.r)

        # --- squash & stretch (mola)
        pl.stretch_v += (1 - pl.stretch) * 350 * dt
        pl.stretch_v *= max(0.0, 1 - 9 * dt)
        pl.stretch += pl.stretch_v * dt
        pl.stretch = clamp(pl.stretch, 0.55, 2.0)

        # --- energia: só recarrega parado
        if not moving and pl.dash_t <= 0 and pl.vel.length() < 40:
            pl.energy = min(100, pl.energy + 22 * (1 + pl.mods["regen"]) * dt)

        # --- espinhos
        edge = min(pl.pos.x, W - pl.pos.x, pl.pos.y, H - pl.pos.y) - pl.r
        if edge < SPIKE - 4:
            center = Vector2(W / 2, H / 2)
            if pl.hurt(12, from_pos=pl.pos + (pl.pos - center), knock=450):
                pass  # o empurrão já aponta pro centro

        # --- tiro
        mouse_v = Vector2(mouse)
        aim = mouse_v - pl.pos
        aim_dir = aim.normalize() if aim.length_squared() > 0 else Vector2(1, 0)
        if buttons[0] and pl.shoot_cd <= 0:
            pl.shoot_cd = 0.2 / (1 + pl.mods["rate"])
            hand = pl.pos + aim_dir * (pl.r + 14)
            self.bullets.append({
                "p": hand, "v": aim_dir * 820 * (1 + pl.mods["bspeed"]),
                "life": 1.4, "dmg": 10 * (1 + pl.mods["dmg"])})

        # --- tiros do player
        for b in self.bullets:
            b["p"] += b["v"] * dt
            b["life"] -= dt
            for e in self.enemies:
                if e.try_hit(b["p"], b["dmg"]):
                    b["life"] = 0
                    if random.random() < 0.08 + pl.mods["frag"]:
                        self.spawn_fragment(e.pos)
                    break
        self.bullets = [
            b for b in self.bullets
            if b["life"] > 0 and 0 < b["p"].x < W and 0 < b["p"].y < H]

        # --- inimigos
        for e in self.enemies:
            e.update(dt, self)
            if e.pos.distance_to(pl.pos) < e.a * 0.6 + pl.r:
                pl.hurt(15, from_pos=e.pos)
        for e in self.enemies:
            if e.dead:  # explosãozinha
                for _ in range(24):
                    v = from_angle(random.uniform(0, math.tau)) * random.uniform(80, 320)
                    self.particles.append({"p": Vector2(e.pos), "v": v, "life": 0.6, "max": 0.6, "r": random.uniform(2, 6)})
        self.enemies = [e for e in self.enemies if not e.dead]

        # --- tiros inimigos
        for b in self.enemy_bullets:
            b["p"] += b["v"] * dt
            if pl.bullet_inv <= 0 and b["p"].distance_to(pl.pos) < pl.r + 5:
                if pl.hurt(10, from_pos=b["p"], knock=200):
                    b["p"].update(-999, -999)
        self.enemy_bullets = [
            b for b in self.enemy_bullets if -20 < b["p"].x < W + 20 and -20 < b["p"].y < H + 20]

        # --- pulso (habilidade especial)
        for pu in self.pulses:
            pu["r"] += 520 * dt
            for b in self.enemy_bullets:
                if b["p"].distance_to(pu["p"]) < pu["r"] + 8:
                    b["p"].update(-999, -999)
            for i, e in enumerate(self.enemies):
                if i not in pu["hit"] and e.pos.distance_to(pu["p"]) < pu["r"] + e.a:
                    pu["hit"].add(i)
                    if e.shield > 0 and e.armor > 0:
                        e.break_shield()
                        self.add_text("escudo quebrado!", e.pos.x, e.pos.y - e.a - 20, GOLD, life=1.2)
        self.pulses = [p for p in self.pulses if p["r"] < 280]

        # --- fragmentos de energia
        for f in self.fragments:
            f["t"] -= dt
            f["p"] += f["v"] * dt
            f["v"] *= 0.95
            d = pl.pos - f["p"]
            if d.length() < 110 and d.length_squared() > 0:
                f["p"] += d.normalize() * 280 * dt
            if d.length() < pl.r + 8:
                pl.energy = min(100, pl.energy + 20)
                f["t"] = 0
        self.fragments = [f for f in self.fragments if f["t"] > 0]

        # --- morreu?
        if pl.hp <= 0:
            pl.hp = 0
            self.state = "over"
            return

        # --- sala limpa -> perk
        if self.state == "play" and not self.enemies:
            self.state = "clear"
            self.clear_timer = 2.2
            pl.energy = min(100, pl.energy + 30)
            self.add_text("Sala limpa!", W / 2, 140, WHITE, big=True)
            if len(pl.perks) < 6:
                perk = roll_perk()
                pl.add_perk(perk)
                name, col = RARITIES[perk["rarity"]][0], RARITIES[perk["rarity"]][1]
                self.add_text(f"{name}: {perk['name']}  ({perk['text']})", W / 2, 195, col, life=3.0)
            else:
                self.add_text("Perks cheios!", W / 2, 195, GOLD)
        elif self.state == "clear":
            self.clear_timer -= dt
            if self.clear_timer <= 0:
                self.next_room()

    # ---------------------------------------------------------- desenho
    def draw_player(self, surf, mouse):
        pl = self.player
        if pl.invuln > 0 and int(pl.invuln * 20) % 2 == 0:
            return
        s = pl.stretch
        pts = ellipse_points(pl.pos.x, pl.pos.y, pl.r * s, pl.r / s, pl.stretch_ang)
        pygame.draw.polygon(surf, WHITE, pts)
        # mão
        aim = Vector2(mouse) - pl.pos
        aim_dir = aim.normalize() if aim.length_squared() > 0 else Vector2(1, 0)
        pygame.draw.circle(surf, WHITE, pl.pos + aim_dir * (pl.r + 14), 6)

    def draw_hud(self, surf, mouse):
        pl = self.player
        cx = W // 2
        # vida
        hb = pygame.Rect(cx - 190, H - 98, 380, 18)
        pygame.draw.rect(surf, (32, 32, 42), hb, border_radius=3)
        fill = hb.copy()
        fill.width = int(hb.width * pl.hp / pl.max_hp)
        pygame.draw.rect(surf, (235, 80, 90), fill, border_radius=3)
        pygame.draw.rect(surf, (90, 90, 105), hb, 1, border_radius=3)
        # energia (menor e mais fina)
        eb = pygame.Rect(cx - 150, H - 74, 300, 7)
        pygame.draw.rect(surf, (32, 32, 42), eb, border_radius=2)
        fill = eb.copy()
        fill.width = int(eb.width * pl.energy / 100)
        pygame.draw.rect(surf, BLUE, fill, border_radius=2)
        # slots de perk
        hover = None
        for i in range(6):
            c = (cx + int((i - 2.5) * 46), H - 44)
            if i < len(pl.perks):
                col = RARITIES[pl.perks[i]["rarity"]][1]
                pygame.draw.circle(surf, col, c, 15, 3)
                pygame.draw.circle(surf, col, c, 6)
                if Vector2(mouse).distance_to(c) < 17:
                    hover = (pl.perks[i], c)
            else:
                pygame.draw.circle(surf, WHITE, c, 15, 2)
        if hover:
            perk, c = hover
            name, col = RARITIES[perk["rarity"]][0], RARITIES[perk["rarity"]][1]
            l1 = font_b.render(f"{perk['name']} - {name}", True, col)
            l2 = font.render(perk["text"], True, WHITE)
            w = max(l1.get_width(), l2.get_width()) + 20
            box = pygame.Rect(0, 0, w, 52)
            box.midbottom = (c[0], c[1] - 24)
            pygame.draw.rect(surf, (28, 28, 38), box, border_radius=6)
            pygame.draw.rect(surf, col, box, 1, border_radius=6)
            surf.blit(l1, (box.x + 10, box.y + 6))
            surf.blit(l2, (box.x + 10, box.y + 28))
        # infos
        surf.blit(font_b.render(f"Sala {self.room}", True, WHITE), (SPIKE + 12, SPIKE + 10))
        help_txt = "WASD mover  |  ESPAÇO dash  |  esq. atirar  |  dir. pulso (35 energia)  |  parado recarrega energia"
        surf.blit(font.render(help_txt, True, (90, 90, 105)), (SPIKE + 12, SPIKE + 34))

    def draw(self, mouse):
        screen.fill(BG)
        for x in range(0, W, 80):
            pygame.draw.line(screen, GRID, (x, 0), (x, H))
        for y in range(0, H, 80):
            pygame.draw.line(screen, GRID, (0, y), (W, y))
        screen.blit(self.spike_surf, (0, 0))

        for f in self.fragments:
            blink = f["t"] > 3 or int(f["t"] * 8) % 2 == 0
            if blink:
                pygame.draw.circle(screen, BLUE, f["p"], 6)
                pygame.draw.circle(screen, (200, 230, 255), f["p"], 3)

        for e in self.enemies:
            e.draw(screen)

        for b in self.bullets:
            pygame.draw.circle(screen, WHITE, b["p"], 4)
        for b in self.enemy_bullets:
            pygame.draw.circle(screen, (255, 90, 90), b["p"], 5)

        # camada com transparência: fantasmas do dash, partículas, pulsos
        overlay.fill((0, 0, 0, 0))
        for g in self.ghosts:
            a = int(110 * g["life"] / g["max"])
            s = g["s"]
            pts = ellipse_points(g["p"].x, g["p"].y, 16 * s, 16 / s, g["ang"])
            pygame.draw.polygon(overlay, (220, 235, 255, a), pts)
        for p in self.particles:
            a = int(255 * p["life"] / p["max"])
            pygame.draw.circle(overlay, (255, 255, 255, a), p["p"], p["r"])
        for pu in self.pulses:
            a = int(255 * (1 - pu["r"] / 280))
            pygame.draw.circle(overlay, (190, 225, 255, a), pu["p"], pu["r"], 4)
        screen.blit(overlay, (0, 0))

        if self.state != "over":
            self.draw_player(screen, mouse)
        self.draw_hud(screen, mouse)

        for t in self.texts:
            f = big_font if t["big"] else font_b
            img = f.render(t["t"], True, t["c"])
            img.set_alpha(int(255 * min(1, t["life"] / (t["max"] * 0.4))))
            screen.blit(img, img.get_rect(center=t["p"]))

        if self.state == "over":
            img = big_font.render("Você morreu", True, RED)
            screen.blit(img, img.get_rect(center=(W // 2, H // 2 - 20)))
            img = font_b.render(f"Chegou até a sala {self.room}  -  aperte R pra tentar de novo", True, WHITE)
            screen.blit(img, img.get_rect(center=(W // 2, H // 2 + 25)))

        # mira
        pygame.draw.circle(screen, WHITE, mouse, 8, 1)
        pygame.draw.circle(screen, WHITE, mouse, 1)
        pygame.display.flip()


# ----------------------------------------------------------------- loop principal
def main():
    game = Game()
    while True:
        dt = min(clock.tick(60) / 1000, 0.05)
        mouse = pygame.mouse.get_pos()
        keys = pygame.key.get_pressed()
        buttons = pygame.mouse.get_pressed()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if ev.key == pygame.K_SPACE:
                    game.try_dash(keys, mouse)
                if ev.key == pygame.K_r and game.state == "over":
                    game.reset()
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
                game.try_special(mouse)

        game.update(dt, keys, mouse, buttons)
        game.draw(mouse)


if __name__ == "__main__":
    main()
