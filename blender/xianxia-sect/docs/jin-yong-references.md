# Jin Yong references for /sect

This is a menu of Jin Yong 金庸 (Jīn Yōng) references to hide in the /sect fly-through. Four specialists each brainstormed one novel. I merged their ideas, cut the weak and crowded ones, and checked every fact that survived against the novel text or a reliable reference. Corrections to the specialists' drafts are listed near the end.

The four novels, and the short names used below:

- 射雕英雄传 (Shè Diāo Yīngxióng Zhuàn, *The Legend of the Condor Heroes*): **Condor**.
- 神雕侠侣 (Shén Diāo Xiálǚ, *The Return of the Condor Heroes*): **Return**.
- 倚天屠龙记 (Yǐtiān Túlóng Jì, *Heaven Sword and Dragon Saber*): **Heaven Sword**.
- 笑傲江湖 (Xiào'ào Jiānghú, *The Smiling, Proud Wanderer*): **Wanderer**.

The first three are one family saga, the Condor Trilogy. Wanderer stands alone, but it shares one legend with Return: the swordsman 独孤求败 (Dúgū Qiúbài, "Alone, Seeking Defeat"). A word that comes up everywhere is 江湖 (jiānghú, literally "rivers and lakes"), the martial-arts underworld where these stories happen.

**Already in progress.** `spec.md` now makes the sect the Ming Cult 明教 (Míngjiào) from Heaven Sword. The client UI already says "The Ming Cult". Some Blender files still say 月华宗 (Yuèhuá Zōng, "Moonlit Sect"). The two stone monoliths at the gate are becoming the Heaven Sword 倚天剑 (Yǐtiān Jiàn) and the Dragon Saber 屠龙刀 (Túlóng Dāo). The formation track (`music/sect-themes/09-formation.md`) was rewritten today as "The Stone Guardian Wakes". Every idea below assumes those changes. Nothing in the repo was edited for this document.

**How to read the ideas.**

- **Effort.** S = text or config only. M = client code, or one small Blender prop plus a rebake of that one area on the box. L = a new Blender set piece plus a rebake.
- **Chapters** follow the standard 40-chapter editions. Where the newest revision 新修版 (xīnxiū bǎn, the early-2000s "new revised edition") changes a fact, the idea says so.
- **Quotes.** Jin Yong's text is still under copyright, so site text quotes only short phrases from him. Older poems the novels quote (Yue Fei, Qiu Chuji, Yuan Haowen, Li Bai) are public domain.
- **Card** means a lore card: the text panel that opens when a visitor clicks a named spot (`AREA_THINGS` in `client/src/lib/sect/content.ts`). Cards cost nothing visually, so most deep cuts live there.

---

## Top picks

These six give the most delight for the least work, and together they touch all four novels.

1. **Formation music: the sleeping guardian (Formation, idea Fo1).** It answers your current ask directly: a guardian that is still and patient until provoked, then overwhelming. It also fixes a key problem in the current prompt.
2. **Strike the sword against the saber (Gate, G1).** It is the secret the sect's own novel is built around, it reuses the monoliths you are already building, and it needs no rebake.
3. **The arena's giant sword becomes the Heavy Iron Sword (Arena, A1).** One material and shape change ties three novels together, because this iron was later melted into the saber at the gate.
4. **Five techniques on the five stele rows, and the Nine Swords on the master stele (Steles, St1 and St2).** It is mostly text, and the Heaven Sword story of a manual with nineteen confidently wrong lines is the best hallucination metaphor in wuxia.
5. **"Where Zhang Wuji buried the manuals" in the Cave Abode (Abode, Ab3).** The abode already looks exactly like that hidden valley, and the carving's own wish ("will anyone find these, centuries from now?") turns the visitor into the person who found them.
6. **The novel's last page at the summit, plus three golden needles on the contact card (Summit, Su1 and Su2).** Return ends on a mountaintop, under the moon, with a goodbye and a promise to answer any request. So does the flight. Both are S.

---

## Ideas by area, in flight order

### Gate 山门 (shānmén, Mountain Gate), frame 93, Hero section

The two blade monoliths are already becoming the Heaven Sword and the Dragon Saber. Two guardian lions flank the stair top. Build G1 first. G2 and G3 are small add-ons.

#### G1. Strike the sword against the saber (signature)

- **What the visitor does:** click the sword, then the saber (or tap one, then the other). Both jade cores flare, a deep bronze bell rings, and hairline cracks of light run up both blades. Two glowing slips drift toward the camera. One is labelled 武穆遗书 (Wǔmù Yíshū, "Book of Wumu", the war manual of the general Yue Fei). It opens the Hackathon Playbook link already in the Experience data, with the line "Yue Fei's art of war was hidden in the saber. Mine is about hackathons." The other is labelled 九阴真经 (Jiǔyīn Zhēnjīng, the Nine Yin Manual) and flies the visitor to the Stele Forest. The saber's cracks seal after a few seconds. The sword's cracks fade more slowly, with a card line: "The smith who mended the saber refused to mend the sword." A plain "Strike them together" button in the gate reader gives keyboard and screen-reader users the same reward.
- **The reference:** before the city of Xiangyang fell, Guo Jing 郭靖 (Guō Jìng) and Huang Rong 黄蓉 (Huáng Róng) had the pair forged. They hid the Book of Wumu in the saber, and the Nine Yin Manual plus the key teachings of the Eighteen Dragon-Subduing Palms 降龙十八掌 (Xiánglóng Shíbā Zhǎng) in the sword. Strike one against the other and both break, giving up what is inside. The whole rhyme about the saber "commanding all under heaven" turns out to mean a war manual. Later, Wu Jincao 吴劲草 (Wú Jìncǎo) of the Ming Cult's Sharp Metal Banner re-forges the broken saber, but refuses to repair the sword, because its owner's school had killed so many Ming Cult brothers.
- **Edition note:** in the 新修版 the blades hold iron slips with a map to Peach Blossom Island instead of the books themselves. Say "hidden in the blades" and the line works in every edition.
- **Why fans will love it:** it is the mystery the novel chases for forty chapters, and the slow-healing sword is a deep cut only readers will catch. Everyone else gets a small ritual with a real reward.
- **Effort:** M (client only, reuses the monolith meshes, no rebake). Split the `gate-swords` named spot into `gate-sword` and `gate-saber`.
- **Risks:** keep the cracked look brief so the hero view never looks damaged. Sound stays opt-in.

#### G2. The golden-maned lion and the Lion's Roar

- **What the visitor sees and does:** the lion on the saber's side gets a gold mane. Its card says the saber's most famous owner was a lion king who carried it to an island of ice and fire. Hidden: press and hold that lion for two seconds and it roars. A low roar, petals blown off the plaza, a ripple through the clouds below. The card adds: "Stuff your ears with cloth, the way Zhang Cuishan and Yin Susu did."
- **The reference:** 谢逊 (Xiè Xùn), the Golden-Haired Lion King 金毛狮王 (Jīnmáo Shīwáng), is one of the Ming Cult's four Dharma Kings. At a gathering on Wangpan Island 王盘山 (Wángpán Shān), he takes the Dragon Saber and uses the Lion's Roar 狮子吼 (shīzi hǒu) to knock out every other guest. Only Zhang Cuishan 张翠山 (Zhāng Cuìshān) and Yin Susu 殷素素 (Yīn Sùsù), whose ears were stuffed with cloth, stay standing.
- **Why fans will love it:** a golden lion guarding the saber is Xie Xun at a glance, and a voice used as a weapon fits a builder of voice-first systems.
- **Effort:** S for the card. M for the gold mane (material change plus gate rebake, or a client material override) and the roar.
- **Risks:** no camera shake under reduced motion. Keep the roar short and more grand than scary.

#### G3. The saber rhyme on the plinths

- **What the visitor sees:** each monolith's plinth carries half of the famous rhyme in weathered characters. Under the saber: 武林至尊，宝刀屠龙 (wǔlín zhìzūn, bǎodāo túlóng, "Supreme in the martial world is the precious saber, Dragon Slayer"). Under the sword: 倚天不出，谁与争锋 (yǐtiān bù chū, shéi yǔ zhēngfēng, "Unless the Heaven Sword comes out, who can rival it?"). The middle line, 号令天下，莫敢不从 (hàolìng tiānxià, mò gǎn bù cóng, "It commands all under heaven; none dare disobey"), goes to the forge (F2).
- **The reference:** the rhyme drives the whole plot. On Wangpan Island, Zhang Cuishan leaps up a cliff and carves all 24 characters into the rock as a calligraphy duel. Xie Xun stares at the three lines and says "我写不出，是我输了" ("I can't write that. I lose.").
- **Effort:** M (text on two plinths, gate rebake). Carving all three lines on the cliff beside the upper stair landing is the L version.
- **Risks:** it is Jin Yong's own verse, so keep to these short halves. Keep it weathered and off-axis so it never competes with the gate plaque.

### Mirror 心镜台 (Xīnjìng Tái, Heart-Mirror Terrace), frame 217, About section

A calm, personal area. Allow one visible addition (M1). M2 and M3 live in cards and hover effects.

#### M1. The Nine Yang couplet on the pond pavilion

- **What the visitor sees:** a vertical couplet in gold on dark boards, on the two front columns of the hexagonal pond pavilion: 他强由他强，清风拂山冈 ｜ 他横任他横，明月照大江 (tā qiáng yóu tā qiáng, qīngfēng fú shāngāng ｜ tā hèng rèn tā hèng, míngyuè zhào dàjiāng). In English: "Let him be strong: a clear breeze brushing the hills. Let him rage: the bright moon on the great river."
- **The reference:** this is the core verse of the Nine Yang Manual 九阳真经 (Jiǔyáng Zhēnjīng). Zhang Wuji 张无忌 (Zhāng Wújì), the hero of Heaven Sword and later leader of the Ming Cult, memorised it without understanding it. Standing still to take three palm strikes from the abbess Miejue 灭绝师太 (Mièjué Shītài), he suddenly gets it: however strong or fierce the enemy, treat the blow like a breeze over a hill or moonlight on a river.
- **Why fans will love it:** it is the most quoted line of the novel's philosophy, it ends on the moon, and it sits beside a pond that reflects a mirror. It also matches About card 01, "Most of my work is failure handling": stay calm under load.
- **Effort:** M (two boards with text, mirror rebake). The same lines as an epigraph in the About reader is S.
- **Risks:** online copies mix 由 and 任. The wording above follows the novel text. It must be legible at the camera distance, or it should go in the reader instead.

#### M2. 过 and 改之: "mistake" and "fix it"

- **What the visitor sees:** the mirror's card reads: "The hero of an old story was named Guo, which means 'mistake'. His courtesy name, Gaizhi, means 'fix it'. The mirror shows you both." Optional: the two characters carved small on the mirror's lotus cradle.
- **The reference:** Yang Guo 杨过 (Yáng Guò), hero of Return, has the courtesy name 改之 (Gǎizhī). He was named so that he would know his faults and correct them, and not repeat his father's path. In the standard edition Guo Jing chose the name; in the 新修版, Huang Rong did. The card avoids naming who.
- **Why fans will love it:** the About section's first card is about failure handling, and the hero's name is literally "mistake, fix it".
- **Effort:** S for the card. M for the carving.
- **Risks:** none worth noting.

#### M3. "Who am I?" in the bronze (hidden)

- **What the visitor sees:** after several clicks on the mirror, the reflection flips upside down for about two seconds and two faint lines ripple across it: 「我是谁？」「你就是你。」 (wǒ shì shéi? nǐ jiù shì nǐ, "Who am I?" "You are you."). Then the About text settles in as normal.
- **The reference:** Condor, chapter 40, the second Contest of Mount Hua. Ouyang Feng 欧阳锋 (Ōuyáng Fēng) has trained the Nine Yin Manual backwards and fights upside down. Huang Rong beats him with words: she says the one man he can never beat is "Ouyang Feng". He asks "我是谁？", she answers "你就是你", and he flees from his own shadow. The upside-down flip is the in-joke.
- **Why fans will love it:** the About section is literally "who I am". Non-readers just see a quiet line about identity.
- **Effort:** S to M (a CSS overlay pinned to the mirror, or a flip of the reflection texture).
- **Risks:** the joke is about a villain losing his mind. Keep it a soft two-second ripple, only after repeated clicks.

### Forge 炼器峰 (Liànqì Fēng, Artifact Forge Peak), frame 352, Projects section

The forge has almost no references yet. It is the natural home for the story of how the gate's blades were made.

#### F1. Where the blades came from

- **What the visitor sees:** the cauldron's card gains one line: "Long ago, a master smith melted a black iron sword with fine Western metal and cast a saber and a sword from it. The saber now stands at the gate. The rest of the story is on the arena."
- **The reference:** in the standard edition, Guo Jing and Huang Rong had the Heavy Iron Sword 玄铁重剑 (xuántiě zhòngjiàn) melted with 西方精金 (xīfāng jīngjīn, "fine metal from the West") into both the Dragon Saber and the Heaven Sword. In the 新修版, the iron went into the saber only, and the sword was cast from Yang Guo's and Xiaolongnü's Gentleman and Lady swords 君子剑 / 淑女剑 (Jūnzǐ Jiàn / Shūnǚ Jiàn). The line above names only the saber for the iron, so it is true in every edition.
- **Why fans will love it:** flying gate, then forge, then arena, the visitor travels backwards through the blades' family tree.
- **Effort:** S.
- **Risks:** none.

#### F2. 号令天下 on the command flag

- **What the visitor sees:** DispatchAI's artifact is already a command flag (`FORGE_RING` in `forge.py`). Its card borrows the middle line of the saber rhyme: 号令天下 ("commands all under heaven"), "for an AI that dispatches 911 calls".
- **Effort:** S.
- **Risks:** keep it to the four characters so it reads as a nod, not a boast.

### Arena 论剑台 (Lùnjiàn Tái, Sword-Discussion Arena), frame 516, Hackathons section

The arena's name already points to the Contests of Mount Hua 华山论剑 (Huàshān Lùnjiàn), the tournaments that crown the greatest fighters in the Condor Trilogy. Build A1 and A2. A3 rides inside A1's card.

#### A1. The giant sword becomes the Heavy Iron Sword (signature)

- **What the visitor sees:** the colossal sword that pierces the island turns near-black iron. Its cyan glow strip becomes a very faint ember red, as if red light shows through the black. The edges are thick and blunt, the guard and pommel plain dark iron, and the tip that pokes out under the island becomes round like a half-sphere. Carved on the stone where the blade enters the island: 重剑无锋 ｜ 大巧不工 (zhòngjiàn wú fēng ｜ dà qiǎo bù gōng, "A heavy sword needs no edge. Great skill needs no tricks.").
- **The reference:** Return, chapter 26 神雕重剑 ("The Condor and the Heavy Sword"). In Dugu Qiubai's Sword Tomb, Yang Guo finds a plain sword far heavier than any weapon: deep black with a faint red light inside, blunt on both edges, the tip "round like a half-sphere". The eight characters are carved on the stone beneath it.
- **Why fans will love it:** the gate's blades get their ancestor in the same flight, and the round tip under the island is a detail only readers will notice. Everyone else sees a huge black blade with a smouldering core over a white arena.
- **Effort:** M (materials, tip shape, two text columns in `arena.py` `_build_sword`, arena rebake).
- **Risks:** black and red can read as "evil". Keep the red emission low (about 2 to 4) and let the gold banners carry the colour. Keep the weight (64 jin in the standard edition, 81 in the 新修版) out of visible text.

#### A2. Mount Hua: the old and new Five Greats

- **What the visitor sees:** a small 华山论剑 under the Hackathons title. Hover: "The first Contest of Mount Hua: five masters fought seven days and seven nights for the Nine Yin Manual. Mine last a weekend." On the arena floor, five small bronze plates at the compass points. Each plate shows two titles, the first contest's holder and the third contest's holder:
  - East 东: 东邪 (Dōngxié, "Eastern Heretic") Huang Yaoshi 黄药师 (Huáng Yàoshī), who held the seat both times.
  - West 西: 西毒 (Xīdú, "Western Venom") Ouyang Feng, then 西狂 (Xīkuáng, "Western Madman") Yang Guo. Hover: "The west seat is Bill's: West Coast, 36 wins, some madness required."
  - South 南: 南帝 (Nándì, "Southern Emperor") Duan Zhixing 段智兴 (Duàn Zhìxīng), then 南僧 (Nánsēng, "Southern Monk") Yideng 一灯 (Yīdēng). Same man, who gave up his throne to become a monk.
  - North 北: 北丐 (Běigài, "Northern Beggar") Hong Qigong 洪七公 (Hóng Qīgōng), then 北侠 (Běixiá, "Northern Hero") Guo Jing.
  - Centre 中, on the taiji: 中神通 (Zhōng Shéntōng, "Central Divinity") Wang Chongyang 王重阳 (Wáng Chóngyáng), then 中顽童 (Zhōng Wántóng, "Central Imp") Zhou Botong 周伯通 (Zhōu Bótōng). Hover: "The most solemn spot in the arena belongs to the prankster."
- **The reference:** the first contest happens before Condor begins: five masters fight for seven days and seven nights over the Nine Yin Manual, and Wang Chongyang wins the title 天下第一 (tiānxià dìyī, "number one under heaven"). The five became the Five Greats 五绝 (wǔjué). In Return's last chapter, the survivors rename the five: Huang Rong gives Yang Guo the word 狂 ("mad"), and Huang Yaoshi puts the carefree Zhou Botong at the centre, saying he ranks first of all because he never cared about fame.
- **Why fans will love it:** the arena tells the whole trilogy on one floor, and the prankster in the centre is the book's own joke.
- **Effort:** S if the plates are client decals on the flat floor. M if carved in Blender (arena rebake).
- **Risks:** 天下第一 can read as boastful, so it never appears on the banner. Place the plates by world compass after the arena's assembly yaw, not by local axes.

#### A3. The Sword Tomb, told in the sword's card

- **What the visitor sees:** the Heavy Iron Sword's card tells Dugu Qiubai's four swords as four stages of a career:
  - A sharp sword, "used before twenty" (弱冠前, ruòguān qián): Bill's first win came at 17.
  - A soft sword, thrown into a valley after it hurt a good man by mistake: the lesson learned the hard way.
  - This heavy sword, "with it he crossed the world unopposed before forty": the grand prizes.
  - A rotted wooden sword: "after forty, grass, wood, bamboo and stone can all be a sword." Bill reached that stage early: he judges now.
  - Last line: "His name means 'alone, seeking defeat'. Bill still enters a few a year."
- **The reference:** Return, chapter 26. The cliff boulder reads 剑冢 (jiànzhǒng, "Sword Tomb") and "剑魔独孤求败既无敌于天下，乃埋剑于斯" ("The Sword Demon Dugu Qiubai, having no rival under heaven, buried his swords here"). Each sword slot has one carved line for one stage of his life. The soft sword's slot holds only a stone strip, because he threw that sword away.
- **Effort:** S. Building the cairn and the four slots on the rear pier is an M option, but it would crowd the arena.
- **Risks:** a bragging tone. Keep the self-aware lines above.

### Mission 任务殿 (Rènwù Diàn, Mission Hall), frame 619, Experience section

Seven jade tablets for seven roles. Pick Mi1 for the tablets. Mi2 and Mi3 are card text.

#### Mi1. The seven tablets as the Big Dipper Formation

- **What the visitor sees:** the seven tablets hang in the shape of the Big Dipper instead of a row, each carrying one star name: 天枢 (Tiānshū), 天璇 (Tiānxuán), 天玑 (Tiānjī), 天权 (Tiānquán), 玉衡 (Yùhéng), 开阳 (Kāiyáng), 摇光 (Yáoguāng). If the tablets cannot move, the Experience timeline in the UI draws its seven markers as the Dipper instead.
- **The reference:** Condor. The Seven Masters of Quanzhen 全真七子 (Quánzhēn Qīzǐ) fight in the 天罡北斗阵 (Tiāngāng Běidǒu Zhèn, "Big Dipper Formation"), each seated at one star, from Ma Yu 马钰 (Mǎ Yù) at Tianshu to Sun Bu'er 孙不二 (Sūn Bù'èr) at Yaoguang. When one is attacked, the neighbours strike back, as if one person had seven people's skill. Tianquan is the dimmest star but sits where the bowl meets the handle, so the strongest master, Qiu Chuji 丘处机 (Qiū Chǔjī), holds it. They fight Huang Yaoshi to a standstill at the inn in Ox Family Village. When Huang Yaoshi later works out that the formation's weak point lies at the Pole Star, Guo Jing jumps in and holds the Pole Star's position himself.
- **Bonus for you:** put the role you see as your turning point at Tianquan.
- **Why fans will love it:** seven roles, seven stars. Fans will spot it at once, and to everyone else it is astronomy.
- **Effort:** M for the UI-only version. L for moving the tablets in Blender (mission rebake).
- **Risks:** low. Heaven Sword's Wudang formation was also proposed for these tablets, but its details could not be confirmed, so it was cut.

#### Mi2. 侠之大者 on the Dispatch AI tablet

- **What the visitor sees:** the Dispatch AI tablet's card opens with 侠之大者 (xiá zhī dà zhě, "the greatest kind of hero") and: "An old general told a young hero that the greatest heroes serve their country and its people. Dispatch AI triaged emergency calls."
- **The reference:** Return, chapter 20, titled 侠之大者. Guo Jing tells the young Yang Guo: 为国为民，侠之大者 (wèi guó wèi mín, xiá zhī dà zhě, "Serving the country and the people: that is the greatest hero"). It is often credited to Condor, but this is where he says it.
- **Why fans will love it:** it is the most quoted line in the trilogy.
- **Effort:** S. A small plaque on the mission wall is M.
- **Risks:** 为国 ("for the country") can read as political on a US portfolio. Show only 侠之大者 in large text and keep the full line inside the card.

#### Mi3. The bell's strangest appointment

- **What the visitor sees:** the mission bell's card: "It rang the day a hard-drinking swordsman, thrown out of his own school, was made head of a sect of nuns. Careers take odd turns."
- **The reference:** Wanderer. The dying abbess Dingxian 定闲师太 (Dìngxián Shītài) asks Linghu Chong 令狐冲 (Lìnghú Chōng) to lead the Hengshan sect 恒山派 (Héngshān Pài), whose members are nearly all nuns, and he accepts.
- **Effort:** S.
- **Risks:** none.

### Library 藏经阁 (Cángjīng Gé, Scripture Pavilion), frame 772, Education section

Calm area. Two text lines, no new props.

#### L1. The man who proofread 5,481 scrolls

- **What the visitor sees:** a hover note on the pagoda: "Huang Shang proofread all 5,481 scrolls of the Daoist canon and came out a grandmaster. I finished a four-year degree in two and a half."
- **The reference:** Condor, chapter 16 九阴真经 ("The Nine Yin Manual"). Zhou Botong tells how the emperor had 黄裳 (Huáng Cháng, often romanised Huang Shang) print the Daoist canon 万寿道藏 (Wànshòu Dàozàng), 5,481 scrolls. Afraid a mistake would cost him his head, Huang Shang read every scroll and taught himself martial arts along the way. The twist for this site: the enemies he later wrote the Nine Yin Manual to defeat were Ming Cult fighters. The trilogy's most famous manual exists because someone needed to beat this sect.
- **Why fans will love it:** a library is the right place for the manual's origin story, and it lines up with Bill's real 2.5-year degree.
- **Effort:** S.
- **Risks:** the 1950s serial edition gave the manual a different author. Every edition in print today uses Huang Shang.

#### L2. "Three schools, one path"

- **What the visitor sees:** the Education heading already reads "Three schools, one path." Its card adds: "Dying, the monk Jueyuan recited the Nine Yang Manual once. Three listeners each kept a part, and carried it into three schools: Emei, Shaolin and Wudang. One got its height, one its breadth, one its purity."
- **The reference:** the end of Return and the opening of Heaven Sword. The monk 觉远 (Juéyuǎn) recites the manual before he dies. Guo Xiang 郭襄 (Guō Xiāng) founds Emei 峨嵋 (Éméi), the monk Wuse 无色 (Wúsè) takes his part to Shaolin 少林 (Shàolín), and the boy Zhang Junbao 张君宝 (Zhāng Jūnbǎo) becomes Zhang Sanfeng 张三丰 (Zhāng Sānfēng), founder of Wudang 武当 (Wǔdāng). The novel sums up the three as 高 (gāo, height), 博 (bó, breadth) and 纯 (chún, purity).
- **Effort:** S.
- **Risks:** none.

### Steles 碑林 (bēilín, Stele Forest), frame 974, Skills section

Five stele rows already map to the five phrases of the skills line (`skillGroups()` in `content.ts`). Three specialists wanted this area, so here is one merged plan: one technique per row, the Nine Swords on the master stele.

#### St1. Five rows, five techniques

Each row's view gains one technique and one line:

- **voice-first: Lion's Roar 狮子吼.** "On Wangpan Island, Xie Xun beat an entire gathering with his voice alone. The two guests who stuffed their ears were the only ones left standing." (Heaven Sword. Pairs with G2.)
- **agents: Holy Fire Tokens 圣火令 (Shènghuǒ Lìng).** "见圣火令如见教主 (jiàn Shènghuǒ Lìng rú jiàn jiàozhǔ): to see the token is to see the leader. Whoever holds it acts with the leader's authority. That is what an agent with tools is. Guard the token." (Heaven Sword, chapter 29, where envoys from Persia demand obedience in the token's name. The tokens are the Ming Cult's own symbol of command.)
- **latency: Heaven-and-Earth Net 天罗地网势 (tiānluó dìwǎng shì).** "Keep 81 sparrows inside the space in front of your chest with bare hands, and let none escape. Your hands must be faster than a sparrow." (Return, chapter 6 玉女心经. Xiaolongnü 小龙女 (Xiǎolóngnǚ) trains Yang Guo this way, ending with 九九八十一只麻雀, "nine nines, eighty-one sparrows". The 新修版 adds an easier first stage with a different name.)
- **keeping a human in the loop: Jade Maiden Pure-Heart Sword 玉女素心剑法 (Yùnǚ Sùxīn Jiànfǎ).** "A sword art for two. One fights in one school's style, the other in another's, and each covers the other's openings." (Return. It is the last chapter of the Jade Maiden manual. Its author, Lin Chaoying 林朝英 (Lín Cháoyīng), wrote it imagining fighting beside the man she loved.)
- **when the model is wrong: the nineteen lines of the Great Shift 乾坤大挪移 (Qiánkūn Dà Nuóyí).** "The manual's last level had nineteen lines that sounded right and were wrong. Their author had never reached that level; he imagined it. Zhang Wuji skipped them, and that saved him." (Heaven Sword, chapter 20. The novel says forcing those lines would have meant madness, paralysis or death.)

- **Why fans will love it:** every pairing is a famous moment, and the last one is a real point about AI: a confident manual written by someone who never tested it is the oldest hallucination story in wuxia.
- **Effort:** S as reader text. M for a small plaque at the head of each row (`steles.py`, steles rebake).
- **Risks:** none. Leave out the Bat King's blood-drinking and any other dark detail.

#### St2. The master stele: the Nine Swords of Dugu

- **What the visitor sees:** the 8 m gold-glyph master stele's card: "Every move has a flaw. The art is finding it first." Hidden layer: if the visitor stops at the steles and touches nothing for about 12 seconds, the stele slowly brightens and one line fades in: 根本无招，如何可破？ (gēnběn wú zhāo, rúhé kě pò, "If there is no move at all, what is there to break?"). The winning move was to do nothing.
- **The reference:** 独孤九剑 (Dúgū Jiǔ Jiàn, the Nine Swords of Dugu), Dugu Qiubai's sword art, taught by the old master Feng Qingyang 风清扬 (Fēng Qīngyáng) to Linghu Chong on the Cliff of Reflection, Wanderer chapter 10 传剑 ("Passing On the Sword"). Its nine forms are 总诀式, 破剑式, 破刀式, 破枪式, 破鞭式, 破索式, 破掌式, 破箭式, 破气式: a general formula, then the breaking of sword, saber, spear, whip, rope, palm, arrow and inner energy. The card line comes from chapter 26: 只要有招，便有破绽 (zhǐyào yǒu zhāo, biàn yǒu pòzhàn, "wherever there is a move, there is a flaw"). The hidden line is what Linghu Chong mutters in chapter 10 when he finally understands.
- **Why fans will love it:** it fits Bill's skills line ("what happens when the model is wrong") and his eval work. The idle trigger is a joke only readers get.
- **Effort:** S for the card. M for the idle reveal (client). L for carving the nine form names as new glyph columns (steles rebake).
- **Risks:** the reveal is a gentle fade and never moves the camera. An alternative master-stele line from Condor is the Nine Yin Manual's opening, 天之道，损有余而补不足 ("The Way of Heaven takes from what has too much and gives to what has too little"), which is Laozi chapter 77 and public domain. Pick one.

### Scroll 玉简阁 (Yùjiǎn Gé, Jade Slip Pavilion), frame 1103, Resume section

#### Sc1. The manual everyone fought over

- **What the visitor sees:** the resume card adds: "The Nine Yin Manual started fights across three novels. This scroll is free to take."
- **The reference:** across the trilogy, people kill, steal and go mad for the Nine Yin Manual. Return's last chapter sums it up: the struggle over it "spread bloodshed across the land" (流血天下, liúxuè tiānxià).
- **Effort:** S.
- **Risks:** none.

### Formation 护宗大阵 (Hùzōng Dàzhèn, Grand Sect-Protecting Formation), frame 1208, Architecture section

This is where your new music note lands. Build Fo1 to Fo4. Fo5 is a big swing for later. Fo6 lives in the site-wide easter eggs.

#### Fo1. Music: the sleeping guardian (top pick)

Your note asks for slow, ponderous music for an ancient stone golem that is peaceful until provoked, then answers with heaven-shaking might. Three specialists independently pitched the same shape, each from a different novel. Here is the merged plan.

- **The story behind it (Heaven Sword, chapter 36 夭矫三松郁青苍, "Three Pines, Twisting and Green").** On a lone peak behind Shaolin, three ancient monks, 渡厄 (Dù'è), 渡劫 (Dùjié) and 渡难 (Dùnàn), sit inside hollows cut into three pine trunks, guarding a prisoner in a pit between the trees. They do not move. When intruders come, their black ropes strike: 似缓实急，却又无半点风声 (sì huǎn shí jí, "they seemed slow but were really fast, and made no sound of wind"), at night, in pouring rain. Once the ropes close into the Vajra Demon-Subduing Circle 金刚伏魔圈 (Jīngāng Fúmó Quān), the novel says not eight attackers, not sixteen, not thirty-two could break in. Even Zhang Wuji, the strongest fighter alive, cannot. That is your stone golem, in story form. (A fun twist for fans: the sect's guardian is modelled on the Ming Cult's toughest opponents.)
- **The rule for the sound (Condor, chapter 12 亢龙有悔, "The Proud Dragon Has Regrets").** Hong Qigong explains that the palm's secret lies not in 亢 (kàng, "soaring") but in 悔 (huǐ, "holding back"): "打出去的力道有十分，留在自身的力道却还有二十分" (hit with ten parts of force and keep twenty in reserve). That is the brief for the loud part: even at full fury, the guardian should sound like it is holding most of its strength back. The power comes from weight, not speed.
- **What the visitor hears:** at rest, a slow, immense calm. Single deep drum strikes far apart like a heartbeat, stone chimes 编磬 (biānqìng, an ancient Chinese instrument made of tuned stone slabs, which suits a stone guardian), low bronze bells, a hollow xun 埙 (xūn, clay ocarina) breathing a slow line, low bowed strings and bass sheng moving together like one body, far thunder and rain. Provoked, the same pulse erupts: drums on every downbeat landing like mountain footsteps, gong crashes, roaring low suona, bronze bells at full force. Same tempo throughout. Then it settles back.
- **Fix this either way.** The current `09-formation.md` asks for "F# minor pentatonic (yu mode)". F# minor pentatonic is F#, A, B, C#, E. The C# is not one of the site's five shared notes (D, E, F#, A, B), so it can clash when tracks crossfade. The README's own yu mode is B minor pentatonic (B, D, E, F#, A). Its troubleshooting fallback, "D minor pentatonic", is worse: D, F, G, A, C shares only two notes with the set. Use "B minor pentatonic (yu mode)". If you want F# to stay the home note, use the README's jue wording instead: "pentatonic centered on F# (jue mode, D major key signature)". The README table row for 09 should match.
- **Two ways to build it:**
  1. **Simplest (S):** keep the current single track (calm, fury, calm, all at 60 BPM) and only fix the key. It already follows your brief.
  2. **Interactive (M):** make two loops in the same key and tempo, a rest loop and a wake loop. Make the wake loop with Suno's Cover from the rest take with Audio Influence high, the same way the README makes the summit from the gate, so key and structure match. Start both together, the wake loop at zero volume. When the visitor provokes the formation (Fo2), fade the wake loop up over about half a second, hold about 8 bars (32 s at 60 BPM, where one bar is 4 s), then fade back over about 6 s. Check each take's real tempo before trimming.
- **Suno Style, rest loop** (no names, per the README rule):
  `Chinese ancient temple instrumental, slow, ponderous and immovable, a colossal stone guardian asleep on a sacred mountain, B minor pentatonic (yu mode), 60 BPM, half-time feel, single deep dagu strikes far apart like a slow heartbeat, low bianqing stone chimes, large low bronze bells, hollow xun melody in long breaths, low gehu and bass sheng moving together in slow unison, faint fast gehu tremolo far underneath, distant thunder and rain, vast stone-hall reverb, immense power held still, same mood throughout, loop-friendly, soft background level`
- **Suno Style, wake loop** (Cover of the rest take):
  `Chinese ancient epic instrumental, the stone guardian wakes with heaven-shaking might, B minor pentatonic (yu mode), 60 BPM, still slow and heavy, never faster, massive dagu and paigu drums on every downbeat like mountain footsteps, huge gong crashes, roaring low suona and guanzi, low gehu tremolo surging, bianzhong bronze bells at full force, thunderclaps, terrifying weight with a steady tempo, same mood throughout, loop-friendly, loud but controlled`
- **Exclude styles** (both): `vocals, singing, humming, choir, chant, female vocals, wordless vocals, fast tempo, speed up, arpeggio, ostinato, EDM, trance, techno, synthwave, electric guitar, rock drums, drum kit, backbeat, heavy metal, trap, dubstep, pop, Japanese, taiko, march, flamenco`. "ostinato" stays excluded on purpose: repeating patterns are what made an earlier version sound like a machine.
- **Titles (they do not change the sound):** 夭矫三松 (Yāojiǎo Sān Sōng, "Three Pines") for the rest loop and 金刚伏魔圈 ("The Vajra Circle") for the wake loop. Or keep "The Stone Guardian Wakes 护宗大阵".
- **Effort:** S for the prompts. M for the two-loop switch once music playback exists on /sect (the README says playback is a separate job).
- **Risks:** Suno may drift tempo on the Cover, so check BPM before trimming. Never borrow any TV or film theme (see "Things to avoid").

#### Fo2. Provoke the formation

- **What the visitor does:** click the floating array core three times. The wake loop swells (Fo1), the light beams whip around the plaza like the three black ropes, and the dome flashes like lightning. About 30 seconds later everything settles. Under reduced motion, only the music changes.
- **Effort:** M (client).
- **Risks:** it must never hide the formation's light diagram, which is the Architecture content.

#### Fo3. The Ming Cult's Five Element Banners

- **What the visitor sees:** the four service clusters are already coloured fire red, wood green, water blue and metal white (`CLUSTER_STYLE` in `formation.py`). Their banners carry the names of the Ming Cult's five banner corps 五行旗 (Wǔxíng Qí): 烈火 (Lièhuǒ, Raging Fire), 巨木 (Jùmù, Giant Wood), 洪水 (Hóngshuǐ, Great Flood) and 锐金 (Ruìjīn, Sharp Metal). The core dais gets a gold-yellow ring marked 厚土 (Hòutǔ, Thick Earth), the fifth element. The formation card says: "Four services and one core fly the banners of the Ming Cult's five element corps."
- **The reference:** Heaven Sword. The five banners are the Ming Cult's fighting units, and the ones who hold the line when six orthodox sects besiege the Cult's headquarters, Bright Peak 光明顶 (Guāngmíng Dǐng). Wu Jincao of the Sharp Metal Banner is the smith in G1.
- **Why fans will love it:** the colours are already there. The names make the diagram readable as the Ming Cult's army without adding anything.
- **Effort:** S as card text. M to put the names on the banners (`FLAG_CHARS`, formation rebake). One option keeps the trigram characters on the pillars and puts the banner names on the cluster flags only.
- **Risks:** five-element theory makes water black, but blue reads better here. Keep it.

#### Fo4. The Star-Absorbing Method on the agent step

- **What the visitor sees:** under pillar 02, "LLM agent", whose real text already mentions the jailbreak guardrail, one extra line: "Star-Absorbing Method 吸星大法 (Xīxīng Dàfǎ): pull in other people's power without filtering it, and sooner or later it turns on you. That is why a guardrail reads every message first."
- **The reference:** Wanderer. Linghu Chong learns the method by accident from words carved into the iron bed of a prison cell under West Lake (chapter 21 囚居, "Imprisoned"). The method absorbs opponents' inner energy, but foreign energies clash inside the absorber and eventually backfire. Shaolin's abbot says only the 易筋经 (Yìjīn Jīng, Sinew-Changing Classic) can dissolve them.
- **Why fans will love it:** it is an accurate metaphor for prompt injection, and engineers who read Jin Yong will enjoy it.
- **Effort:** S (one map of extra lines in `lib/sect`). Keep `content-copy.ts` unchanged, because a test pins its main-page wording.
- **Risks:** keep it one line under the technical text, never above it.

#### Fo5. Big swing: the Divine Condor asleep by the rear gate

- **What the visitor sees and does:** on a weathered rock just outside the formation's rear gate, facing the core, sits a huge, ugly, ancient bird, taller than a person (scale it to about 4 m so it reads). Sparse yellow-black feathers, a hooked beak, a bald head with a blood-red lump, thick legs, short wings. It never flies. At rest it breathes and slowly turns its head to follow the camera. When the formation is provoked (Fo2), it spreads its short wings and gives one cry. Card: "Old, ugly, and in no hurry. It walks everywhere. Don't poke it."
- **The reference:** Return, chapter 23 手足情仇. The novel's words: 那雕身形甚巨，比人还高，形貌丑陋之极 ("the condor was enormous, taller than a man, and ugly in the extreme"), with sparse feathers, a blood-red lump on its head, thick legs and wings too short to explain how it could fly. It strides around with its head high. In its first scene it kills a giant venomous python with its beak. It was Dugu Qiubai's companion, and it later trains Yang Guo with the heavy sword. The 神雕 (shéndiāo, "Divine Condor") is in the novel's title.
- **Why fans will love it:** the sect is full of elegant cranes, and this is one scruffy bird that refuses to fly. It is also your stone golem made flesh.
- **Effort:** L (a new creature model, a formation rebake for its light and shadow, client code for the head turn and wing spread).
- **Risks:** a cheap-looking bird ruins the mood. Keep it mostly still and partly weathered, half statue, half alive. Build it only if the creature can look AAA.

### Abode 洞府 (dòngfǔ, Cave Abode), frame 1380, Personal section

The busiest area in the brainstorms, so the strictest limit. Ab1 and Ab2 are hover text on existing facts and cost nothing visually. Pick one cave secret: Ab3 (recommended) or Ab4. Ab5 is optional life.

#### Ab1. Huang Rong's menu on the noodles fact

- **What the visitor sees:** hovering "Still chasing the best bowl of noodles in San Francisco" unfolds a tiny paper menu: 叫化鸡 (jiàohuā jī, Beggar's Chicken) · 玉笛谁家听落梅 (yùdí shéi jiā tīng luò méi, "Whose Jade Flute Plays Falling Plum Blossoms") · 好逑汤 (hǎoqiú tāng, "The Gentleman's Match Soup") · 二十四桥明月夜 (èrshísì qiáo míngyuè yè, "Moonlit Night at Twenty-Four Bridges"). Caption: "Huang Rong cooked her way into Hong Qigong's lessons. I'd trade a lesson for a good bowl of noodles too."
- **The reference:** Condor, chapter 12. Huang Rong feeds the glutton Hong Qigong so that he will teach Guo Jing. One dish is meat strips cut like flutes from five meats, with 25 flavour combinations. Another is 24 tofu balls steamed inside a whole ham, after which the ham is thrown away. The dish names come from classic poems (the Book of Songs and Du Mu's line about Yangzhou's twenty-four bridges), so non-fans just read poetry.
- **Effort:** S to M (copy plus a small hover card).
- **Risks:** keep it to the four names. Do not paste the recipe passages.

#### Ab2. Left hand a square, right hand a circle

- **What the visitor sees:** a hover note on "Plays drums and piano": 「左手画方，右手画圆」 (zuǒshǒu huà fāng, yòushǒu huà yuán, "left hand draws a square, right hand a circle"). "Zhou Botong invented fighting with each hand on its own, alone in a cave for fifteen years. Drummers call it limb independence."
- **The reference:** Condor, chapter 17 双手互搏 (shuāngshǒu hùbó, "The Two Hands Spar"). Zhou Botong, trapped on Peach Blossom Island for fifteen years, invents the technique out of boredom. A proverb says no one can draw a square and a circle at once, and that is exactly where training starts. Guo Jing learns it. In Return, Xiaolongnü learns it too.
- **Why fans will love it:** the abode is a cave, and drums and piano need exactly this skill.
- **Effort:** S. An optional touch-screen mini-game (draw a square and a circle with two fingers at once, and the moon gate glows) is M.
- **Risks:** none.

#### Ab3. 张无忌埋经处: where Zhang Wuji buried the manuals (top pick)

- **What the visitor sees:** six small, unpainted characters scratched low on the cave wall near the moon gate, readable only up close: 张无忌埋经处 (Zhāng Wújì mái jīng chù, "where Zhang Wuji buried the manuals"). Click: "Three books are buried behind this wall: the Nine Yang Manual, a healer's casebook and a poisoner's handbook. He wondered whether anyone would ever find them, centuries from now. You did." Optional: a white ape on a ledge above the pool.
- **The reference:** Heaven Sword, chapter 16 剥极而复参九阳. Zhang Wuji crawls through a narrow tunnel into a hidden valley in the Kunlun mountains, with fruit trees and a waterfall. He operates on a white ape's belly and finds the lost Nine Yang Manual inside, wrapped in oilcloth. Five years later, before leaving, he buries it in the cave wall with the healer Hu Qingniu's 胡青牛 (Hú Qīngniú) medical book and the poisoner Wang Nangu's 王难姑 (Wáng Nángū) poison book, scratches the six characters with a sharp stone, and wonders whether anyone will find them "千百年后" (hundreds or thousands of years later).
- **Why fans will love it:** the abode already is that valley: a cliff, a cave, a waterfall into a pool. Six characters make it a place fans know, and Zhang Wuji goes on to lead the Ming Cult.
- **Effort:** M (small text via `U.text` in `abode.py`, next to the existing 洞天福地 carving, abode rebake, one named spot such as `abode-buried-manuals`). The ape is a separate M prop.
- **Risks:** keep it small so it stays a discovery, not a sign.

#### Ab4. Alternative cave secret: the Ancient Tomb behind the moon gate

- **What the visitor sees:** inside the lit moon-gate tunnel, a pale blue-green jade slab with a thin cold mist (the cold jade bed 寒玉床, hányù chuáng), and one rope strung across the chamber at head height. Above the gate, two massive stone slabs held in a slot, with a thin trickle of sand from a hole beside it. Card: "Two slabs, over ten thousand jin, held up by sand. Pull one round stone, the sand runs out, and the door shuts forever. Best not to touch anything."
- **The reference:** Return. The Ancient Tomb 活死人墓 (Huó Sǐrén Mù) on Mount Zhongnan, built by Wang Chongyang. Yang Guo sleeps on the cold jade bed to speed up his training (chapter 6). The school's lightness training reaches the point where you can sleep on a rope. The Dragon-Severing Stone 断龙石 (duànlóng shí) in chapter 7 is exactly this: a round stone, a hole, running sand, slabs over ten thousand jin that took more than a hundred men to install.
- **Effort:** M (small props, abode rebake; the sand can be a client particle).
- **Risks:** it competes with Ab3 for the same cave, so pick one. Do not print 活死人墓 ("tomb of the living dead") anywhere but the card, since "tomb" is an odd word for a home.

#### Ab5. Optional life: jade bees with a message on their wings

- **What the visitor sees:** about a dozen slow, pale, glowing bees drift around the peach trees. Hovering one makes it land, and its card shows a close-up drawing of tiny characters on its wings: 我在绝 on the left, 情谷底 on the right ("I am at the bottom of Passionless Valley"). Card: "Someone at the bottom of a valley pricked this into bee wings with a needle and let them go."
- **The reference:** Return, chapter 38 生死茫茫. Xiaolongnü survives sixteen years at the bottom of 绝情谷 (Juéqíng Gǔ, Passionless Valley) and pricks the six characters into jade bees' wings with a fine needle, each as small as a grain of rice. Huang Rong later finds about thirty hives at the valley floor.
- **Effort:** M (reuse the butterfly system in `client/src/lib/sect/life.ts` with a new look, one card illustration).
- **Risks:** clutter around the abode's seven fact hotspots. The text appears only in the card, never in 3D.

### Summit 望月台 (Wàngyuè Tái, Moon-Gazing Summit), frame 1647, Contact section

Three novels want the summit. Rule: one line on the final frame (Su1). Everything else goes in cards.

#### Su1. The novel's last page, under the moon (top pick)

- **What the visitor sees:** as the moon fills the frame, one line of calligraphy fades in: 他日江湖相逢，再当杯酒言欢 (tārì jiānghú xiāngféng, zài dāng bēijiǔ yánhuān), with "If our paths cross again someday, let's share a drink and laugh." Then the contact panel appears.
- **The reference:** Return, chapter 40 华山之巅 ("The Summit of Mount Hua"). Yang Guo says goodbye with this line and walks down the mountain with Xiaolongnü and the condor. The next sentence is 其时明月在天 (qí shí míngyuè zài tiān, "at that moment the bright moon hung in the sky"), and the novel closes on Li Bai's poem 秋风清，秋月明 ("clear autumn wind, bright autumn moon").
- **Why fans will love it:** the flight ends where the novel ends: a summit, the moon, a goodbye. The farewell is also a perfect "contact me" line.
- **Effort:** S (summit text plus a fade on the final frames).
- **Risks:** none. Keep it the only text on that frame.

#### Su2. Three golden needles on the contact card (top pick)

- **What the visitor sees:** the three ways to reach Bill (email, the voice orb, LinkedIn) each get a small gold needle icon with a glint. Heading: "Three golden needles. Send any one and I'll answer." Small print: "Out of needles? Ask anyway."
- **The reference:** Return, chapter 35 三枚金针 (sān méi jīnzhēn, "Three Golden Needles"). Yang Guo gives the girl Guo Xiang three golden needles: show one, and he will do one thing she asks. In the last chapter he tells her 虽无金针，仍可来要我为你办到 ("even without a needle, you can still come and ask me").
- **Effort:** S (copy plus a small SVG icon in the /sect content, not the main page's components).
- **Risks:** draw the needle like a slim gold hairpin, not a medical needle. Do not describe what she used the needles for: the third was a plea that he not give up on living, which is far too heavy for a contact card.
- **Alternative:** Heaven Sword's ending gives a lighter version. Zhang Wuji owes Zhao Min 赵敏 (Zhào Mǐn) three favours that break no code of honour. Her third, in the last chapter: "我的眉毛太淡，你给我画一画" ("My eyebrows are too pale. Paint them for me."). Copy: "Three requests, none against the code of the jianghu: write to me, talk to me, take the resume. (Hers was to have her eyebrows painted. These are easier.)" Use the needles or this, not both.

#### Su3. Yue Fei's moonlit line on the arch card

- **What the visitor sees:** the crescent arch's card carries 好山好水看不足，马蹄催趁月明归 (hǎo shān hǎo shuǐ kàn bù zú, mǎtí cuī chèn yuè míng guī): "I can't get my fill of these fine hills and waters; the hoofbeats hurry me home by the bright moon."
- **The reference:** a 12th-century poem by the general Yue Fei 岳飞 (Yuè Fēi), public domain. In Condor, chapter 23, Guo Jing and Huang Rong find it carved on a stone tablet in the Cuiwei Pavilion 翠微亭 (Cuìwēi Tíng) on Feilai Peak, under a plaque written by Yue Fei's fellow general Han Shizhong 韩世忠 (Hán Shìzhōng). It is the same Yue Fei whose war manual hides in the saber at the gate.
- **Effort:** S.
- **Risks:** present Yue Fei, a revered national hero, with respect.

#### Su4. Big swing: Ice-Fire Island and the aurora

- **What the visitor sees:** when the summit camera tilts up, a tiny distant islet far to the north, half glacier and half smouldering volcano, with a faint orange, violet and green aurora rippling low behind the moon. Click the islet: "冰火岛 (Bīnghuǒ Dǎo, Ice-Fire Island). An island of ice and fire at the top of the world. A boy was born there, raised by his parents and a blind lion king."
- **The reference:** Heaven Sword, chapter 6 浮槎北溟海茫茫. Drifting north, Zhang Cuishan, Yin Susu and Xie Xun see the northern lights: orange and pale violet, with gold, blue, green and red streaks. The novel says no Chinese person had ever seen them. The sight stops Xie Xun mid-attack in a fit of madness. They land on a volcanic island in the polar sea, which Xie Xun names Ice-Fire Island, and Zhang Wuji is born there.
- **Effort:** L as a baked set piece. M if client-only (a small emissive islet plus an aurora shader, high tier only).
- **Risks:** an aurora at golden hour must stay faint, or it fights the lighting. Skip it on low tiers.

---

## Site-wide ideas

### Loading screen (`client/src/app/sect/loading-screen.tsx`)

#### LS1. The first page of Heaven Sword, plus a pool of loading lines

- **What the visitor sees:** under 明教 / The Ming Sect, one small grey line: 冷浸溶溶月 (lěng jìn róngróng yuè, "steeped cold in the flowing moonlight"), with a few white pear petals drifting. While the scene loads, one line at a time:
  - "Learning the palms one at a time, the way Guo Jing did."
  - "Counting sparrows: 81…"
  - "Cooling the jade bed…"
  - "Waiting for the condor. It walks."
  - "Forgetting the sword form, as instructed."
- **The reference:** Heaven Sword, chapter 1 天涯思君不可忘, opens with the whole of Qiu Chuji's poem 无俗念 (Wú Súniàn, "No Worldly Thoughts"), a poem about pear blossom by moonlight that the novel says was written for Xiaolongnü. Qiu Chuji was a real Daoist master who died in 1227, so the poem is public domain. The loading lines point to Condor chapter 12 (Guo Jing practises one palm for days), St1, Ab4, Fo5 and N2.
- **Effort:** S.
- **Risks:** the phase label is read aloud by screen readers, so keep lines short.

### 404 and broken links

#### N1. 404: lost in the peach-blossom maze

- **What the visitor sees:** peach petals drift over a faint bagua compass. "You've wandered into Huang Yaoshi's peach-blossom maze. Every path looks the same." One button: "Follow Huang Rong out", back to /sect.
- **The reference:** Condor. Peach Blossom Island, home of Huang Yaoshi and his daughter Huang Rong, is laid out as a maze of formations, and outsiders get lost. In chapter 29, Huang Rong thinks of the nine-palace magic square (see E2) as 桃花岛阵图的根基, "the root of the Peach Blossom Island formation plans".
- **Alternative, rotate at random:** the Cliff of Reflection 思过崖 (Sīguò Yá). "Linghu Chong was sent here to face the wall for a year. You only need the Back button." (Wanderer, chapter 8 面壁, "Facing the Wall". That year is when he found the hidden cave and learned the Nine Swords.)
- **Effort:** S to M. There is no `client/src/app/not-found.tsx` yet, only `error.tsx`.
- **Risks:** a root `not-found.tsx` covers every bad URL on the whole site, not just /sect. Decide whether the main site should get the wuxia 404 too.

#### N2. "Forgotten it all?" for bad deep links

- **What the visitor sees:** the note `resolveDeepLink()` writes in `client/src/lib/sect/links.ts` becomes: "Nothing here is called "#xyz". Forgotten it all? 不坏不坏 (bú huài bú huài), not bad at all. Start again from the gate."
- **The reference:** Heaven Sword, chapter 24 太极初传柔克刚. Zhang Sanfeng shows his new Taiji sword once, slowly, then asks Zhang Wuji if he remembers. "I've forgotten a little." Later, "most of it". Finally: "这我可全忘了，忘得干干净净的了" ("Now I've forgotten all of it, completely"). Zhang Sanfeng: "不坏不坏！忘得真快" ("Not bad, not bad! You forgot it fast."). Then Zhang Wuji wins the duel. The point is to keep the idea and drop the form.
- **Effort:** S (string change, update `links.test.ts`).
- **Risks:** none.

### Voice agent (`server/prompts.py`, `server/guardrail.py`)

#### V1. Bill is a Jin Yong fan, with a password

- **What the visitor hears:** one short "Jin Yong fan" section in the passions part of the prompt, and a handful of hidden lines:
  - Say or type 武林至尊 (or "wulin zhizun", or "supreme in the martial world"): the agent answers 宝刀屠龙, then "You know the password. The saber's at the gate," and calls `display_landing_page()`.
  - 倚天不出 gets 谁与争锋.
  - 问世间，情是何物 (wèn shìjiān, qíng shì hé wù, "Ask the world: what is love?") gets the second half, 直教生死相许 ("that two would pledge life and death to each other"), and a note that it is really Yuan Haowen's 13th-century poem, the one Li Mochou sings in Return.
  - "Who am I?": "Careful. Ouyang Feng asked that on Mount Hua and ended up fighting his own shadow."
  - "How long until you reply?": "Less than sixteen years. Email's faster."
  - "Join our sect": a joke about Linghu Chong turning down the cult leader Ren Woxing, who kept asking.
  - 千秋万载，一统江湖 (qiānqiū wànzǎi, yītǒng jiānghú, "for a thousand autumns and ten thousand years, rule all the jianghu"): a laugh that it is the flatterers' chant from Wanderer.
  - Rarely, in text mode, when the guardrail declines an off-topic request: "I'm like Hu Qingniu, the doctor who treats only members of his own sect. Ask me about my projects." (Heaven Sword: Hu Qingniu's nickname is 见死不救, jiàn sǐ bú jiù, "lets the dying die", because he treats only Ming Cult members.)
- **Effort:** S (prompt text), plus adding the novels to the guardrail's allowed passions (the "Yes also for" list near line 281 of `guardrail.py`), then running the guardrail tests.
- **Risks:** without the guardrail change, wuxia talk is refused as off-topic. Speech-to-text may miss Mandarin, so accept pinyin and English triggers too. English TTS mangles Chinese, so keep Chinese lines for text chat. The model must never recite long passages or invent plot; add "if unsure, say you'd have to reread it". Which characters are Bill's favourites has to come from Bill. The "refuses to join" joke fires only on cult phrasing, never on a recruiter.

### Music

- **Mu1. Formation:** see Fo1.
- **Mu2. The flight ends on a qin and xiao duet 曲谐 (Qǔ Xié, "The Tune in Harmony").** A second summit cue for the last frames: the gate's sect theme returns as a call and answer between a guqin 古琴 (gǔqín, seven-string zither) and a xiao 箫 (xiāo, end-blown bamboo flute). They trade phrases, then play together, and on the very last frame one sharp qin note cuts the music off, leaving only the moon. The reference: Wanderer, chapter 7 授谱. At night in the hills, Linghu Chong overhears the swordsman Liu Zhengfeng 刘正风 (Liú Zhèngfēng) on xiao and the cult elder Qu Yang 曲洋 (Qǔ Yáng) on qin, two men from enemy camps, playing the piece they wrote together. It ends: 铮的一声急响，琴音立止 ("with one sharp twang, the qin stopped"), then 唯见明月当空 (wéi jiàn míngyuè dāngkōng, "only the bright moon, high in the sky"). In the last chapter, 曲谐, Linghu Chong (qin) and Ren Yingying 任盈盈 (Rèn Yíngyíng) (xiao) play it at their wedding, finally fulfilling the composers' wish to heal the feud between their sides. Effort: S for a Suno prompt, M for the end-cue playback. Risks: the chapter 7 duet is the two composers' last performance before they die, so frame the cue around the wedding, not the deathbed. The novel never writes the tune down, so any original melody is fine. Do not title the track 笑傲江湖, which pulls toward the famous film song; use 曲谐.

### Hidden easter eggs

#### E1. The four treasures of Plum Manor

- **What the visitor does:** a small seal stamp appears in the corner of four existing detail views: 琴 (qín, the zither) at the mirror's pond pavilion, 棋 (qí, go) at the abode's tea table, 书 (shū, calligraphy) on the resume's jade slip, 画 (huà, painting) at the library's lotus pond. Clicking a stamp pockets that treasure. A four-slot tray tracks progress (saved in localStorage, wrapped in try/catch). When all four are found, four rusty keys turn one after another, and a hidden reader opens: "The prisoner under the lake". It could hold Bill's Jin Yong bookshelf, or the duet from Mu2.
- **The reference:** Wanderer, chapters 19 打赌 ("The Wager") and 20 入狱 ("Into the Prison"). To reach a prisoner kept under West Lake, Linghu Chong and Xiang Wentian tempt the four masters of Plum Manor 梅庄 (Méi Zhuāng), who each love one art: Huangzhong Gong 黄钟公 (qin), Heibai Zi 黑白子 (go), Tubi Weng 秃笔翁 (calligraphy) and Danqing Sheng 丹青生 (painting). The bait: the qin score 《广陵散》 (Guǎnglíng Sǎn), the go record 《呕血谱》 (Ǒuxuè Pǔ, "The Blood-Vomiting Game"), Zhang Xu's 张旭 calligraphy 《率意帖》 (Shuàiyì Tiè), and Fan Kuan's 范宽 painting 《溪山行旅图》 (Xīshān Xínglǚ Tú, *Travelers Among Mountains and Streams*). The cell door needs four keys, one carried by each master, and the locks are thick with rust.
- **Why fans will love it:** fans recognise the four treasures instantly. Everyone else gets a classic "collect four" hunt that pulls them through four areas, and two of the treasures are real masterpieces.
- **Effort:** M (client only).
- **Risks:** visitors may never find it. Hint at it from the voice agent. If you show the real Fan Kuan painting, the painting is public domain, but check the licence of the specific photo.

#### E2. The "23" riddle (formation console)

- **What the visitor does:** the browser console (and a hidden input in the Architecture section) prints Huang Rong's riddle: 「今有物不知其数，三三数之剩二，五五数之剩三，七七数之剩二」 ("There is a number. Divided by 3 it leaves 2, by 5 it leaves 3, by 7 it leaves 2. What is it?"). Typing 23 provokes the formation (Fo2).
- **The reference:** Condor, chapter 29 黑沼隐女. Huang Rong solves the hermit Yinggu's 瑛姑 (Yīnggū) puzzles, recites the nine-palace magic square 九宫 (jiǔgōng): "二四为肩，六八为足，左三右七，戴九履一，五居中央", then writes three problems in the sand. The third is this one, a classic called the 鬼谷算题 (Guǐgǔ suàntí, "Ghost Valley problem"), which mathematicians know as the Chinese Remainder Theorem.
- **Effort:** S.
- **Risks:** 23 is the smallest answer; 23 plus any multiple of 105 also works, so accept those. Keep it out of the visible UI.

#### E3. Guo Xiang's birthday fireworks

- **What the visitor sees:** once a year, ten fireworks shells burst one after another over the moon, each hanging in the sky as one character in its own colour: 恭祝郭二姑娘多福多寿 ("Best wishes to the second Miss Guo: much fortune, long life"). There is also a hidden trigger: typing `guoxiang` anywhere on /sect.
- **The reference:** Return, chapter 36 献礼祝寿. For Guo Xiang's sixteenth birthday, Yang Guo's friends set off fireworks made by the famous Hankou craftsman 黄一炮 (Huáng Yīpào); the ten characters each came out a different colour. The standard edition sets the day on the 24th day of the 10th lunar month.
- **Effort:** M (client particles that sample glyphs drawn on a canvas, plus a small table of future lunar dates).
- **Risks:** performance: high tier only, a few thousand particles, about 20 seconds. The 新修版 may move the date, so treat it as edition-specific.

---

## Cross-novel threads

These are the connections fans love most, because they reward knowing all four books.

1. **The iron's family tree (Arena, Forge, Gate).** Dugu Qiubai's Heavy Iron Sword (A1) is melted down at the forge (F1) into the Dragon Saber at the gate (G1), which hides Condor's Nine Yin Manual and Yue Fei's war manual, and is later re-forged by a Ming Cult smith. Flying forward, the visitor sees the family tree in reverse.
2. **Mount Hua (Arena, Steles, 404).** Condor's first and second contests and Return's third (A2) all happen on Mount Hua, and so does Wanderer's Cliff of Reflection, where the Nine Swords are taught (St2, N1).
3. **Dugu Qiubai, the one man in two novels.** His heavy sword and tomb are on the arena (A1, A3), his old condor guards the formation (Fo5), and his Nine Swords crown the steles (St2).
4. **The Nine Yin Manual's life story.** Written by Huang Shang to beat the Ming Cult (L1), fought over at Mount Hua (A2, M3), hidden in the Heaven Sword (G1), and free on the resume (Sc1).
5. **The Nine Yang Manual's life story.** Recited by the dying Jueyuan into three schools (L2), found inside a white ape and buried again by Zhang Wuji (Ab3), and its core verse sits on the mirror (M1).
6. **A moon in every novel.** The site's name came from the moon (art3m1s, Artemis). Each novel gets one moon line along the flight: Heaven Sword's 明月照大江 on the mirror (M1) and 冷浸溶溶月 on the loading screen (LS1), Condor's Yue Fei line on the summit arch (Su3), Return's farewell under 其时明月在天 on the final frame (Su1), and Wanderer's 唯见明月当空 in the closing duet (Mu2). It also fits the sect: 明 (míng, "bright") is 日 (rì, sun) plus 月 (yuè, moon).

---

## Things to avoid

- **Copyrighted melodies.** Never imitate any film or TV score from an adaptation: not 沧海一声笑 (the 1990 film song for Wanderer), not 铁血丹心 or 世间始终你好 (the 1983 TVB Condor songs), not 刀剑如梦 (the 1994 TVB Heaven Sword theme), nothing else. Suno blocks names anyway, so describe sounds in plain words.
- **Long quotes.** Jin Yong's text is still under copyright. On the site, quote phrases of a dozen or so characters at most. Public-domain poems the novels quote can run longer.
- **Images from adaptations or books.** No drama or film stills, no actors' likenesses, no book covers, no illustrations or comic panels from any edition.
- **Cluttering the calm areas.** Mirror, library, steles and abode each get at most one visible addition. Everything else goes in cards and hover text. Text that cannot be read at camera distance belongs in a card.
- **Dark material.** No Sunflower Manual jokes, no Tian Boguang, nothing about Yang Guo's lost arm, no "jump" wording around Heartbreak Cliff, no Liu Zhengfeng massacre, no Yin Zhiping, no Bat King blood-drinking, no deathbed lines played for laughs. Do not describe Guo Xiang's third needle wish.
- **Boasting.** 天下第一 never appears on a banner. Keep the hackathon jokes self-aware.
- **Edition-specific numbers in visible text,** such as the heavy sword's weight or Guo Xiang's birthday month.

---

## Considered and cut

- **Tea pavilion couplet from Peach Blossom Island (Condor).** Legibility at camera distance, and the abode is already full.
- **Zu Qianqiu's eight wine cups (Wanderer).** Duplicates the noodles fact's menu on the same tea table.
- **Golden-basin retirement 金盆洗手 at the judges' pavilion (Wanderer).** Duplicates A3's "now he judges", and the ceremony ends in a massacre.
- **Blackwood Cliff basket lift and the hanging temple (Wanderer).** L effort for background props, and the first belongs to the villains' headquarters.
- **Six Peach Valley Immortals in the peach tree (Wanderer).** Funny, but the mirror is full. A good spare for a later card pass.
- **The green-bamboo qin behind the music fact (Wanderer).** Lovely, but it needs new audio; a spare once music playback exists.
- **A pair of white condors at the summit (Condor).** Would be confused with the Divine Condor, and cranes already fill that role.
- **A tiny red sword-dancer under the summit pine (Condor).** The painting detail it relies on could not be confirmed.
- **Wudang's Zhenwu Seven-Section Formation for the seven tablets (Heaven Sword).** Competes with Mi1, and its details could not be confirmed.
- **Bright Peak for the arena reader (Heaven Sword).** The arena is full. A good spare for the formation card.
- **Yang Guo's long whistle and the jade-bee swarm for the skills rows (Return), the Bat King for latency (Heaven Sword), Condor's martial-art labels for skill groups.** Replaced by stronger matches in St1.
- **Dragon-palm names as loading phase labels (Condor).** Screen readers read the label aloud, and the palm lists differ between editions. One palm line moved into the LS1 pool.
- **The sixteen-year promise as a 404 (Return).** Tied to Heartbreak Cliff, which is about choosing death.

---

## Fact-check notes

Corrections made to the specialists' drafts:

- The left-right technique is 「左手画方，右手画圆」 (square on the left, circle on the right), not the reverse. The claim that Huang Rong failed the test could not be confirmed and was dropped.
- Yue Fei's line reads 好山好水看不足 (in the novel and in the poem), not 好水好山.
- The aurora is in Heaven Sword chapter 6 浮槎北溟海茫茫, not chapter 7.
- Guo Xiang used all three golden needles. The third asked Yang Guo not to give up on living, so "she saves the third" was wrong, and Su2 no longer describes the wishes.
- The Plum Manor prison chapter is 20 入狱, not 探狱.
- "Seven days and seven nights in heavy snow": the seven days are confirmed, the snow is not, so it was dropped. "Mine last 36 hours" is not true of every hackathon, so A2 says "a weekend".
- Zhang Wuji buried the manuals in his cave wall, not beside the pool. Ab3 places the carving on the cave wall.
- The 重剑无锋，大巧不工 inscription is on the stone under the sword in the novel, so A1 carves it where the blade enters the island.
- The Star-Absorbing Method was carved on an iron bed in the cell (chapter 21 囚居). The claim that the absorbed energies killed Ren Woxing was not confirmed and was dropped.
- Chapter numbers for the Wangpan Island scenes and some Wanderer scenes could not be pinned down, so those ideas do not cite chapters.

New tie found while checking: the enemies Huang Shang wrote the Nine Yin Manual to defeat were Ming Cult fighters (L1).

## Sources

Checked against novel text where possible, and against Chinese Wikipedia for edition differences and chapter titles:

- Heaven Sword: [屠龙刀](https://zh.wikipedia.org/zh-cn/%E5%B1%A0%E9%BE%8D%E5%88%80), [倚天剑](https://zh.wikipedia.org/zh-cn/%E5%80%9A%E5%A4%A9%E5%8A%8D), [谢逊](https://zh.wikipedia.org/wiki/%E8%B0%A2%E9%80%8A), [九阳真经](https://zh.wikipedia.org/zh-hans/%E4%B9%9D%E9%99%BD%E7%9C%9F%E7%B6%93), [觉远](https://zh.wikipedia.org/zh-hans/%E8%A7%89%E8%BF%9C), [圣火令](https://zh.wikipedia.org/zh-cn/%E8%81%96%E7%81%AB%E4%BB%A4), [乾坤大挪移 (Baidu)](https://baike.baidu.com/item/%E4%B9%BE%E5%9D%A4%E5%A4%A7%E6%8C%AA%E7%A7%BB/5069911), [胡青牛](https://zh.wikipedia.org/zh-cn/%E8%83%A1%E9%9D%92%E7%89%9B), chapter text: [ch. 6](https://nh5.com/library/chapter/7/6.html), [ch. 16](https://nh5.com/library/chapter/7/16.html), [ch. 29](https://nh5.com/library/chapter/7/29.html), [ch. 36](https://nh5.com/library/chapter/7/36.html), [ch. 40](https://nh5.com/library/chapter/7/40.html), [Wangpan Island carving](http://jinyong.ylib.com/works/v1.0/works/poem-85.htm), [Taiji scene](https://www.jycg.net/10712.html), [ch. 1 and 无俗念](https://yitian.5000yan.com/42011.html), [chapter list](https://zh.wikipedia.org/zh-cn/%E5%80%9A%E5%A4%A9%E5%B1%A0%E9%BE%99%E8%AE%B0), [Nine Yang verse (Baidu)](https://baike.baidu.com/item/%E4%BB%96%E5%BC%BA%E7%94%B1%E4%BB%96%E5%BC%BA/3095176).
- Return: [玄铁重剑](https://zh.wikipedia.org/zh-hans/%E7%8E%84%E9%90%B5%E9%87%8D%E5%8A%8D), [独孤求败](https://zh.wikipedia.org/zh-cn/%E7%8D%A8%E5%AD%A4%E6%B1%82%E6%95%97), [华山论剑](https://zh.wikipedia.org/zh-hans/%E8%8F%AF%E5%B1%B1%E8%AB%96%E5%8A%8D), [杨过](https://zh.wikipedia.org/wiki/%E6%9D%A8%E8%BF%87), [林朝英](https://zh.wikipedia.org/zh-hans/%E6%9E%97%E6%9C%9D%E8%8B%B1_%28%E9%87%91%E5%BA%B8%E5%B0%8F%E8%AA%AA%29), [chapter list](https://zh.wikipedia.org/zh-cn/%E7%A5%9E%E9%9B%95%E4%BE%A0%E4%BE%A3), chapter text: [ch. 6](https://www.99csw.com/book/2181/64772.htm), [ch. 7](https://nh5.com/library/chapter/4/7.html), [ch. 23](https://nh5.com/library/chapter/4/23.html), [ch. 36](https://nh5.com/library/chapter/4/36.html), [ch. 38](https://nh5.com/library/chapter/4/38.html), [ch. 40](https://www.99csw.com/book/2181/64806.htm), [ending lines](https://www.jycg.net/10471.html), [侠之大者](https://en.jinyong.hk/zh-cn/pages/curator).
- Condor: [chapter 40 text](http://www.lovechinese.org/reading/site/story/630), [chapter 12 text](https://nh5.com/library/chapter/3/12.html), [chapter 17 text](https://shediao.5000yan.com/41942.html), [chapter 23 text](https://nh5.com/library/chapter/3/23.html), [chapter 29 text](http://www.xnnut.com/book/39/ac74ef9a60b7e.html), [天罡北斗阵](http://www.hygart.com/e90406.html), [九阴真经](https://zh.wikipedia.org/zh-cn/%E4%B9%9D%E9%99%B0%E7%9C%9F%E7%B6%93), [黄裳 (Baidu)](https://baike.baidu.com/item/%E9%BB%84%E8%A3%B3/3637867), [chapter list](https://zh.wikipedia.org/zh-cn/%E5%B0%84%E9%9B%95%E8%8B%B1%E9%9B%84%E4%BC%A0).
- Wanderer: [独孤九剑](https://zh.wikipedia.org/zh-cn/%E7%8D%A8%E5%AD%A4%E4%B9%9D%E5%8A%8D), [令狐冲](https://zh.wikipedia.org/zh-cn/%E4%BB%A4%E7%8B%90%E5%86%B2), [笑傲江湖 and chapter list](https://zh.wikipedia.org/zh-cn/%E7%AC%91%E5%82%B2%E6%B1%9F%E6%B9%96), chapter text: [ch. 7](https://www.xbiquges.com/zzchapter/dokxmac/7), [ch. 19](https://www.xbiquges.com/zzchapter/dokxmac/19), [ch. 20](https://www.xbiquges.com/zzchapter/dokxmac/20), [ch. 21](https://www.xbiquges.com/zzchapter/dokxmac/21), [duet and wedding passages](http://www.hqband.com/d31982.html).
- Ming Cult banners: [Ming Order overview](https://wuxiasociety.com/ming-order/), [Five Element Banners article](https://www.163.com/dy/article/FDC2O00A0517N434.html).
