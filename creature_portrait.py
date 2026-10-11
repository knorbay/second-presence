"""Frontal, skin-covered intruder and foreshortened hands for the capture."""
import math
import random
import pygame


class FrontCreature:
    def __init__(self):
        self.skull=pygame.Surface((512,704),pygame.SRCALPHA)
        self.jaw=pygame.Surface((512,704),pygame.SRCALPHA)
        self.hand=pygame.Surface((350,460),pygame.SRCALPHA)
        self._build_head();self._build_hand()

    def _build_head(self):
        s=self.skull
        def poly(color,points):pygame.draw.polygon(s,color,points)
        # A long, skin-covered head. Layered contours keep it organic at game scale.
        outline=[(140,363),(109,312),(100,244),(113,159),(133,94),(170,48),(216,29),
                 (271,24),(324,48),(365,91),(385,150),(399,230),(389,311),
                 (356,384),(320,434),(268,461),(211,433),(172,402)]
        poly((61,66,63),outline)
        pygame.draw.ellipse(s,(118,127,115),(119,41,266,346))
        pygame.draw.ellipse(s,(144,149,130),(133,45,228,302))
        pygame.draw.ellipse(s,(163,164,142),(151,54,167,240))
        pygame.draw.ellipse(s,(174,172,148),(168,61,110,193))
        poly((101,112,103),[(298,64),(340,99),(363,164),(373,226),(356,291),(332,263),(338,186)])
        poly((92,100,91),[(126,226),(158,262),(173,333),(216,376),(205,409),(163,374),(132,309)])
        poly((79,84,79),[(369,222),(381,277),(356,345),(338,394),(304,415),(320,345),(337,272)])
        # Mottling follows the actual skin mask; no noise is placed in empty space.
        rng=random.Random(416)
        for _ in range(1800):
            x=rng.randrange(105,394);y=rng.randrange(40,424)
            color=s.get_at((x,y))
            if color.a:
                delta=rng.randrange(-14,11)
                ink=tuple(max(0,min(255,c+delta)) for c in color[:3])
                pygame.draw.circle(s,ink,(x,y),rng.choice((1,1,2,3)))
        # Fine subcutaneous folds, asymmetrical rather than a grinning skull.
        for points in (
            [(167,99),(154,146),(161,183),(148,221)],
            [(313,90),(330,137),(326,176),(343,223)],
            [(146,278),(168,317),(172,362),(195,401)],
            [(365,268),(341,305),(334,361),(302,406)]):
            pygame.draw.lines(s,(69,81,78),False,points,2)
            pygame.draw.lines(s,(143,145,122),False,[(x+3,y) for x,y in points],1)
        # The sockets are almost closed; the gaze is suggested by wet, uneven edges.
        pygame.draw.ellipse(s,(61,69,64),(136,219,93,53))
        pygame.draw.ellipse(s,(69,72,63),(282,209,83,59))
        poly((7,13,16),[(145,238),(163,231),(192,235),(211,249),(194,258),(164,251)])
        poly((7,12,15),[(290,237),(305,221),(337,218),(352,232),(342,250),(310,252)])
        pygame.draw.lines(s,(157,155,131),False,[(145,237),(166,230),(191,234),(207,244)],2)
        pygame.draw.lines(s,(145,148,129),False,[(292,235),(307,221),(337,219)],2)
        pygame.draw.line(s,(77,86,78),(180,241),(187,244),2)
        pygame.draw.line(s,(91,98,84),(318,231),(323,234),2)
        poly((141,143,119),[(232,218),(255,214),(273,253),(276,294),(253,319),(226,286)])
        poly((31,39,38),[(237,281),(244,276),(247,299),(237,304)])
        poly((24,34,34),[(258,284),(264,286),(269,305),(257,306)])
        # A vertical tear continues into the dropped jaw; teeth emerge at odd heights.
        poly((79,60,55),[(212,313),(249,302),(280,312),(314,337),(333,394),(322,488),
                         (289,559),(249,589),(211,558),(176,486),(168,401),(186,346)])
        poly((4,9,13),[(219,325),(248,315),(277,327),(298,354),(312,408),(296,490),
                      (269,555),(244,563),(219,526),(192,456),(186,396),(201,351)])
        poly((43,28,31),[(231,472),(259,457),(278,482),(270,544),(246,560),(228,519)])
        for n in range(7):
            x=199+n*14;y=342+abs(n-3)*6
            length=(25,41,19,36,27,48,22)[n]
            poly((156+n*3,156+n*2,132+n),[(x,y),(x+9,y+2),(x+7,y+length),(x+3,y+length+3)])
            pygame.draw.line(s,(91,93,78),(x+4,y+4),(x+4,y+length-3))
        for n in range(6):
            yy=388+n*19
            pygame.draw.line(s,(132,113,91),(187,yy),(197+(n%2)*4,yy+7),2)
            pygame.draw.line(s,(153,133,109),(311,yy-12),(297-(n%3),yy-4),2)
        j=self.jaw
        pygame.draw.polygon(j,(68,77,72),[(147,320),(155,408),(180,516),(207,583),(255,625),
                            (304,596),(346,519),(364,403),(352,316),(337,335),(331,435),
                            (305,519),(259,580),(218,534),(181,424),(172,337)])
        pygame.draw.lines(j,(125,137,121),False,[(157,342),(166,418),(191,516),(219,570),
                           (255,599),(293,574),(334,509),(350,408),(345,336)],10)
        pygame.draw.lines(j,(175,170,141),False,[(173,411),(198,514),(230,566),(254,582),(291,554)],3)
        for n in range(7):
            x=212+n*12;y=547+round(math.sin(n/6*math.pi)*25)
            length=(28,43,25,38,22,46,29)[n]
            pygame.draw.polygon(j,(164,159,130),[(x,y),(x+9,y+4),(x+6,y-length),(x+3,y-length-2)])
        # Tendons and a few narrow wet highlights, with dark sides under the torch.
        for x in (179,326):
            pygame.draw.line(j,(86,54,52),(x,373),(x+(31 if x<250 else -29),526),3)
            pygame.draw.line(j,(139,122,101),(x+2,385),(x+(30 if x<250 else -28),510),1)
        shade=pygame.Surface((64,88))
        for y in range(88):
            for x in range(64):
                factor=max(.30,1-abs(x-29)/52-y/320)
                value=round(255*factor);shade.set_at((x,y),(value,value,value))
        shade=pygame.transform.smoothscale(shade,(512,704))
        self.skull.blit(shade,(0,0),special_flags=pygame.BLEND_RGB_MULT)
        self.jaw.blit(shade,(0,0),special_flags=pygame.BLEND_RGB_MULT)

    def _build_hand(self):
        s=self.hand
        pygame.draw.polygon(s,(65,51,45),[(28,460),(22,342),(78,284),(105,208),(180,196),
                            (226,254),(197,325),(133,362),(125,460)])
        pygame.draw.lines(s,(143,130,106),False,[(52,460),(49,360),(110,280),(130,223)],15)
        pygame.draw.lines(s,(182,169,135),False,[(102,460),(101,373),(160,286),(160,220)],11)
        for index in range(4):
            root=(110+index*25,258-index*8);joint=(66+index*51,150-index*8)
            knuckle=(59+index*55,87+index*7);tip=(81+index*51,17+index*7)
            points=[root,joint,knuckle,tip]
            pygame.draw.lines(s,(57,43,39),False,points,19-index)
            pygame.draw.lines(s,(166,152,122),False,points,10-index)
            pygame.draw.lines(s,(209,195,158),False,[(x-2,y) for x,y in points],3)
            for point in (joint,knuckle):
                pygame.draw.circle(s,(95,75,62),point,9-index)
                pygame.draw.circle(s,(180,165,133),(point[0]-2,point[1]-2),5-index//2)
            pygame.draw.polygon(s,(133,123,103),[(tip[0]-5,tip[1]+18),(tip[0]+5,tip[1]+14),
                                                (tip[0]+17,tip[1]-13),(tip[0]+3,tip[1])])
        pygame.draw.lines(s,(184,168,132),False,[(202,276),(274,209),(306,163),(312,97)],10)
        pygame.draw.lines(s,(93,73,61),False,[(212,294),(285,220),(318,167)],4)
        for n in range(6):pygame.draw.line(s,(107,78,63),(112+n*12,233),(90+n*14,301),2)

    def draw(self,surface,time,impact,offset):
        w,h=surface.get_size();approach=min(1,time/.34)
        final=min(1,max(0,(time-1.04)/.40))
        head_height=round(h*(.55+.70*approach+.28*final+.14*impact))
        head_width=round(head_height*512/704)
        centre=pygame.Vector2(w*.5,h*.44)+offset;top=centre.y-head_height*.46
        scale=head_width/512;neck=pygame.Vector2(centre.x,top+head_height*.88)
        for side in (-1,1):
            shoulder=neck+pygame.Vector2(side*210,130)*scale
            pygame.draw.line(surface,(61,55,48),neck,shoulder,max(2,round(24*scale)))
            pygame.draw.line(surface,(107,120,109),neck,shoulder,max(2,round(7*scale)))
            for n in range(7):
                rib=neck+pygame.Vector2(side*25,80+n*32)*scale
                end=rib+pygame.Vector2(side*(135-n*9),18)*scale
                pygame.draw.line(surface,(79,92,86),rib,end,max(2,round(6*scale)))
        head=self.skull.copy()
        opening=round(8+final*27+impact*20+math.sin(time*11)**2*10)
        head.blit(self.jaw,(0,opening))
        for side in (-1,1):
            x=256+side*109
            pygame.draw.line(head,(94,45,39),(x,379),(x-side*34,534+opening),3)
        portrait=pygame.transform.smoothscale(head,(head_width,head_height))
        tilt=10*(1-approach)+math.sin(time*2.8)**9*4-2
        portrait=pygame.transform.rotate(portrait,tilt)
        surface.blit(portrait,(round(centre.x-portrait.get_width()/2),round(top)))
        for side in (-1,1):
            height=round(h*(.44+.20*approach+.12*impact))
            hand=pygame.transform.smoothscale(self.hand,(round(height*350/460),height))
            if side==1:hand=pygame.transform.flip(hand,True,False)
            hand=pygame.transform.rotate(hand,side*(7+impact*12))
            x=w*(.07 if side==-1 else .93)-hand.get_width()/2-side*impact*w*.09
            y=h*(.55-.16*approach)-impact*h*.09
            surface.blit(hand,(round(x+offset.x),round(y+offset.y)))
