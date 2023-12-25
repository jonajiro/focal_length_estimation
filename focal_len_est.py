import tkinter as tk            # ウィンドウ作成用
import tkinter.ttk as ttk
from tkinter import filedialog  # ファイルを開くダイアログ用
from PIL import Image, ImageTk  # 画像データ用
import numpy as np              # アフィン変換行列演算用
import os                       # ディレクトリ操作用
import cv2
import itertools

class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.pack()

        self.my_title = "焦点距離推定"  # タイトル
        self.back_color = "#000000"     # 背景色

        # ウィンドウの設定
        self.master.title(self.my_title)    # タイトル
        self.master.geometry("1200x800")     # サイズ

        self.master.bind("<KeyPress>",self.keyp_handler)
        self.master.bind("<KeyRelease>",self.keyr_handler)

        self.pil_image = None           # 表示する画像データ
        self.filename = None            # 最後に開いた画像ファイル名
        self.img_word = None
        self.img_worde = None
        self.params_flg = 0
        self.params = np.zeros(6)

        self.point_data = []
        self.vpoint_data = None
        self.line_indexlist = []
        self.vpoint_indexlist = []
        self.line_index = 0
        self.vpoint_index = 0
        self.ctl_key = 17
        self.CTRL_KEY_ON = 0
        self.select_mode = 0

        self.undistort_view = 0
        self.undis_point = []
        self.undist_flg = 0

        self.prog_var = tk.IntVar()

        self.create_menu()   # メニューの作成
        self.create_widget() # ウィジェットの作成
    # -------------------------------------------------------------------------------
    # メニューイベント
    # -------------------------------------------------------------------------------
    def menu_open_clicked(self, event=None):
        # File → Open
        filename = tk.filedialog.askopenfilename(
            filetypes = [("Image file", ".bmp .png .jpg .tif"), ("Bitmap", ".bmp"), ("PNG", ".png"), ("JPEG", ".jpg"), ("Tiff", ".tif") ], # ファイルフィルタ
            initialdir = os.getcwd() # カレントディレクトリ
            )
        # 画像ファイルを設定する
        self.set_image(filename)

    def menu_reload_clicked(self, event=None):
        # File → ReLoad
        self.set_image(self.filename)

    def menu_opendistcoeff_clicked(self, event=None):
        # File → Open
        filename = tk.filedialog.askopenfilename(
            filetypes = [("CSV file", ".csv")], # ファイルフィルタ
            initialdir = os.getcwd() # カレントディレクトリ
            )
        self.params = np.loadtxt(filename, delimiter=',')
        self.params_flg = 1

    def menu_quit_clicked(self):
        # ウィンドウを閉じる
        self.master.destroy()

    # -------------------------------------------------------------------------------

    # create_menuメソッドを定義
    def create_menu(self):
        self.menu_bar = tk.Menu(self) # Menuクラスからmenu_barインスタンスを生成

        self.file_menu = tk.Menu(self.menu_bar, tearoff = tk.OFF)
        # self.menu_bar.add_cascade(label="Video File", menu=self.file_menu)
        self.menu_bar.add_cascade(label="File", menu=self.file_menu)

        self.file_menu.add_command(label="Image Open", command = self.menu_open_clicked, accelerator="Ctrl+O")
        self.file_menu.add_command(label="Image ReLoad", command = self.menu_reload_clicked, accelerator="Ctrl+R")
        self.file_menu.add_separator() # セパレーターを追加
        self.file_menu.add_command(label="Undist Coeff File Open", command = self.menu_opendistcoeff_clicked, accelerator="Ctrl+U")
        self.file_menu.add_separator() # セパレーターを追加
        self.file_menu.add_command(label="Exit", command = self.menu_quit_clicked)

        self.menu_bar.bind_all("<Control-o>", self.menu_open_clicked) # ファイルを開くのショートカット(Ctrol-Oボタン)

        self.master.config(menu=self.menu_bar) # メニューバーの配置

    def create_widget(self):
        '''ウィジェットの作成'''

        #####################################################
        # ステータスバー相当(親に追加)
        self.statusbar = tk.Frame(self.master)
        self.mouse_position = tk.Label(self.statusbar, relief = tk.SUNKEN, text="mouse position") # マウスの座標
        self.image_position = tk.Label(self.statusbar, relief = tk.SUNKEN, text="image position") # 画像の座標
        self.label_space = tk.Label(self.statusbar, relief = tk.SUNKEN)                           # 隙間を埋めるだけ
        self.image_info = tk.Label(self.statusbar, relief = tk.SUNKEN, text="image info")         # 画像情報
        self.progbar = ttk.Progressbar(self.statusbar,mode="determinate",maximum = 100,variable=self.prog_var)
        self.prog_var.set(0)
        self.mouse_position.pack(side=tk.LEFT)
        self.image_position.pack(side=tk.LEFT)
        self.label_space.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.image_info.pack(side=tk.RIGHT)
        self.progbar.pack(side=tk.RIGHT)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)

        #####################################################
        # 右側フレーム（画像処理用ボタン配置用）
        right_frame = tk.Frame(self.master, relief = tk.SUNKEN, bd = 2, width = 600)
        right_frame.propagate(False) # フーレムサイズの自動調整を無効にする
        lbl_intro0 = tk.Label(right_frame, text = "マウス左ドラッグ：画像移動")
        lbl_intro1 = tk.Label(right_frame, text = "ホイール回転：拡大＆縮小")
        lbl_intro2 = tk.Label(right_frame, text = "Ctrl押下したままマウス右クリック：直線制御点作成")
        lbl_intro3 = tk.Label(right_frame, text = "Ctrl押下せずにマウス右ドラッグ：直線制御点移動")

        # 平行線群戻る
        self.btn_lineback = tk.Button(right_frame, text = "戻る", width = 15, command = self.btn_lineback_click)
        # 平行線番号
        self.lbl_linenum = tk.Label(right_frame, text = "0")
        # 平行線群進む
        self.btn_linenext = tk.Button(right_frame, text = "進む", width = 15, command = self.btn_linenext_click)

        self.btn_lineback["state"] = tk.DISABLED
        self.btn_linenext["state"] = tk.DISABLED

        # 制御点削除
        self.btn_del = tk.Button(right_frame, text = "制御点全削除", width = 15, command = self.btn_del_click)
        # 焦点距離計算
        self.btn_cal = tk.Button(right_frame, text = "焦点距離計算", width = 15, command = self.btn_cal_click)

        # 交差角度
        self.lbl_vangle = tk.Label(right_frame,text='平行線交差角度[deg.]')
        # 交差角度表示
        self.tb_vangle = tk.Entry(right_frame,width=15)
        self.tb_vangle.delete(0, tk.END)
        self.tb_vangle.insert(tk.END,"90.0")

        # 推定焦点距離
        self.lbl_focal1 = tk.Label(right_frame,text="推定焦点距離候補1："+' [pixel]')
        self.lbl_focal2 = tk.Label(right_frame,text="推定焦点距離候補2："+' [pixel]')

        lbl_intro0.grid(row = 0, column = 0, columnspan = 3, sticky=tk.EW)
        lbl_intro1.grid(row = 1, column = 0, columnspan = 3, sticky=tk.EW)
        lbl_intro2.grid(row = 2, column = 0, columnspan = 3, sticky=tk.EW)
        lbl_intro3.grid(row = 3, column = 0, columnspan = 3, sticky=tk.EW)
        self.btn_lineback.grid(row = 4, column = 0, sticky=tk.EW)
        self.lbl_linenum.grid( row = 4, column = 1, sticky=tk.EW)
        self.btn_linenext.grid(row = 4, column = 2, sticky=tk.EW)
        self.btn_del.grid(row = 5, column = 0, columnspan = 3, sticky=tk.EW)
        self.btn_cal.grid(row = 6, column = 0, columnspan = 3, sticky=tk.EW)
        self.lbl_vangle.grid( row = 7, column = 0, columnspan = 1, sticky=tk.EW)
        self.tb_vangle.grid( row = 7, column = 1, columnspan = 2, sticky=tk.EW)
        self.lbl_focal1.grid( row = 8, column = 0, columnspan = 3, sticky=tk.EW)
        self.lbl_focal2.grid( row = 9, column = 0, columnspan = 3, sticky=tk.EW)

        # フレームを配置
        right_frame.pack(side = tk.RIGHT, fill = tk.Y)


        #####################################################
        # Canvas(画像の表示用)
        self.canvas = tk.Canvas(self.master, background= self.back_color)
        self.canvas.pack(expand=True,  fill=tk.BOTH)  # この両方でDock.Fillと同じ

        #####################################################
        # マウスイベント
        self.canvas.bind("<Motion>", self.mouse_move)                       # MouseMove
        self.canvas.bind("<B1-Motion>", self.mouse_move_left)               # MouseMove（左ボタンを押しながら移動）
        self.canvas.bind("<Button-1>", self.mouse_down_left)                # MouseDown（左ボタン）
        self.canvas.bind("<Double-Button-1>", self.mouse_double_click_left) # MouseDoubleClick（左ボタン）
        self.canvas.bind("<MouseWheel>", self.mouse_wheel)                  # MouseWheel

        self.canvas.bind("<B3-Motion>", self.mouse_move_right)               # MouseMove（左ボタンを押しながら移動）
        self.canvas.bind("<Button-3>", self.mouse_down_right)                # MouseDown（左ボタン）
        self.canvas.bind("<ButtonRelease-3>", self.mouse_up_right)                # MouseDown（左ボタン）

    def set_image(self, filename):
        ''' 画像ファイルを開く '''
        if not filename or filename is None:
            return

        # 画像ファイルの再読込用に保持
        self.filename = filename

        # PIL.Imageで開く
        self.pil_image = Image.open(filename)

        # PillowからNumPy(OpenCVの画像)へ変換
        self.cv_image = np.array(self.pil_image)
        # カラー画像のときは、RGBからBGRへ変換する
        if self.cv_image.ndim == 3:
            self.cv_image = cv2.cvtColor(self.cv_image, cv2.COLOR_RGB2BGR)

        if self.params_flg == 0:
            self.params[0] = self.cv_image.shape[1]/2
            self.params[1] = self.cv_image.shape[0]/2
        # 画像全体に表示するようにアフィン変換行列を設定
        self.zoom_fit(self.pil_image.width, self.pil_image.height)
        # 画像の表示
        self.draw_image(self.cv_image)

        # ウィンドウタイトルのファイル名を設定
        self.master.title(self.my_title + " - " + os.path.basename(filename))
        # ステータスバーに画像情報を表示する
        self.image_info["text"] = f"{self.pil_image.width} x {self.pil_image.height} {self.pil_image.mode}"
        # カレントディレクトリの設定
        os.chdir(os.path.dirname(filename))


    # -------------------------------------------------------------------------------
    # マウスイベント
    # -------------------------------------------------------------------------------

    def mouse_move(self, event):
        ''' マウスの移動時 '''
        # マウス座標
        self.mouse_position["text"] = f"mouse(x, y) = ({event.x: 4d}, {event.y: 4d})"

        if self.pil_image is None:
            return

        # 画像座標
        mouse_posi = np.array([event.x, event.y, 1]) # マウス座標(numpyのベクトル)
        mat_inv = np.linalg.inv(self.mat_affine)     # 逆行列（画像→Cancasの変換からCanvas→画像の変換へ）
        image_posi = np.dot(mat_inv, mouse_posi)     # 座標のアフィン変換
        x = int(np.floor(image_posi[0]))
        y = int(np.floor(image_posi[1]))
        if x >= 0 and x < self.pil_image.width and y >= 0 and y < self.pil_image.height:
            # 輝度値の取得
            value = self.pil_image.getpixel((x, y))
            self.image_position["text"] = f"image({x: 4d}, {y: 4d}) = {value}"
        else:
            self.image_position["text"] = "-------------------------"

    def mouse_move_left(self, event):
        ''' マウスの左ボタンをドラッグ '''
        if self.pil_image is None:
            return
        self.translate(event.x - self.__old_event.x, event.y - self.__old_event.y)
        self.redraw_image() # 再描画
        self.__old_event = event

    def mouse_down_left(self, event):
        ''' マウスの左ボタンを押した '''
        self.__old_event = event

    def mouse_down_right(self, event):
        ''' マウスの右ボタンを押した '''
        if self.pil_image is None:
            return

        mouse_posi = np.array([event.x, event.y, 1]) # マウス座標(numpyのベクトル)
        mat_inv = np.linalg.inv(self.mat_affine)     # 逆行列（画像→Cancasの変換からCanvas→画像の変換へ）
        image_posi = np.dot(mat_inv, mouse_posi)     # 座標のアフィン変換
        x = int(np.floor(image_posi[0]))
        y = int(np.floor(image_posi[1]))

        if self.CTRL_KEY_ON == 1 and self.select_mode == 0:#新規直線作製モード
            #新規ポイントを追加
            self.point_data.append([x,y])
            self.line_indexlist.append(self.line_index)
            self.vpoint_indexlist.append(self.vpoint_index)
            self.select_mode = 2
        elif self.CTRL_KEY_ON == 1 and (self.select_mode == 2 or self.select_mode == 3):
            #直線ポイントを追加
            self.point_data.append([x,y])
            self.line_indexlist.append(self.line_index)
            self.vpoint_indexlist.append(self.vpoint_index)
            self.select_mode = 3
        else:
            ind, dist = self.get_npoint(-1,x,y) #最短距離の点のindexとその距離
            if dist < 10:#近傍に点があれば点位置の更新開始
                self.p_ind = ind
                self.select_mode = 1

        cnt = 0
        cnt0 = 0
        l_buf = self.line_indexlist[0]
        for i in range(len(self.vpoint_indexlist)):
            if self.vpoint_indexlist[i] == self.vpoint_index:
                cnt0 = cnt0 + 1
                if l_buf != self.line_indexlist[i]:
                    cnt = cnt + 1
                    cnt0 = 1
                l_buf = self.line_indexlist[i]

        if (cnt > 1  and cnt0 > 1 ) or (cnt > 0 and self.vpoint_index == 0 and cnt0 > 1):
            if self.vpoint_index < 1:
                self.btn_linenext["state"] = tk.NORMAL
            else:#２グループより多い平行線群は作らない
                self.btn_linenext["state"] = tk.DISABLED
        else:
            self.btn_linenext["state"] = tk.DISABLED

        if self.vpoint_index > 0:
            self.btn_lineback["state"] = tk.NORMAL
        else:
            self.btn_lineback["state"] = tk.DISABLED
        self.redraw_image() # 再描画

    def mouse_up_right(self, event):
        ''' マウスの右ボタンを離した '''
        if self.pil_image is None:
            return

        if self.select_mode == 1:
             #点選択モード中に右ボタン離した場合
            self.select_mode = 0
        self.redraw_image() # 再描画

    def mouse_move_right(self, event):
        ''' マウスの右ボタンを押して動かした '''
        if self.pil_image is None:
            return
        # self.redraw_image() # 再描画
        # 画像座標
        mouse_posi = np.array([event.x, event.y, 1]) # マウス座標(numpyのベクトル)
        mat_inv = np.linalg.inv(self.mat_affine)     # 逆行列（画像→Cancasの変換からCanvas→画像の変換へ）
        image_posi = np.dot(mat_inv, mouse_posi)     # 座標のアフィン変換
        x = int(np.floor(image_posi[0]))
        y = int(np.floor(image_posi[1]))

        if self.CTRL_KEY_ON == 0:#直線作製モード
            if self.select_mode == 1:#点選択モード
                self.p_ind = self.update_npoint(self.p_ind,x,y)
        self.redraw_image() # 再描画

    def mouse_double_click_left(self, event):
        ''' マウスの左ボタンをダブルクリック '''
        if self.pil_image is None:
            return
        self.zoom_fit(self.pil_image.width, self.pil_image.height)
        self.redraw_image() # 再描画


    def keyp_handler(self,event):
        if event.keycode == self.ctl_key:
            self.CTRL_KEY_ON = 1


    def keyr_handler(self,event):
        if event.keycode == self.ctl_key:
            self.CTRL_KEY_ON = 0
        if self.CTRL_KEY_ON == 0:
            if self.select_mode == 2:
                #直線選択モード中にコントロールキーが解除された状態で右ボタン離した場合
                self.point_data = self.point_data[:-1]
                self.line_indexlist = self.line_indexlist[:-1]
                self.vpoint_indexlist = self.vpoint_indexlist[:-1]
                self.select_mode = 0
            elif self.select_mode == 3:
                #直線選択モード中にコントロールキーが解除された状態で右ボタン離した場合
                self.line_index = self.line_index + 1
                self.select_mode = 0


    def mouse_wheel(self, event):
        ''' マウスホイールを回した '''
        if self.pil_image is None:
            return

        if (event.delta < 0):
            # 上に回転の場合、縮小
            self.scale_at(0.8, event.x, event.y)
        else:
            # 下に回転の場合、拡大
            self.scale_at(1.25, event.x, event.y)

        self.redraw_image() # 再描画

    # -------------------------------------------------------------------------------
    # マウスカーソル位置取得関係の関数
    # -------------------------------------------------------------------------------
    def update_npoint(self,ind,x,y):
        self.point_data[ind][0] = x
        self.point_data[ind][1] = y
        return ind

    def get_npoint(self,ind,x,y):
        #return 最短距離の点のindex & 最短距離の点までの距離
        dist = []
        for i in range(len(self.point_data)):
            if ind == -1:
                dist.append(np.sqrt((self.point_data[i][0]-x)**2 + (self.point_data[i][1]-y)**2))
            else:
                if self.line_indexlist[i] == ind:
                    dist.append(np.sqrt((self.point_data[i][0]-x)**2 + (self.point_data[i][1]-y)**2))
                else:
                    dist.append(99999)
        ind_e = np.argsort(np.array(dist))
        return ind_e[0], dist[ind_e[0]]
    # -------------------------------------------------------------------------------
    # 画像表示用アフィン変換
    # -------------------------------------------------------------------------------

    def reset_transform(self):
        '''アフィン変換を初期化（スケール１、移動なし）に戻す'''
        self.mat_affine = np.eye(3) # 3x3の単位行列


    def translate(self, offset_x, offset_y):
        ''' 平行移動 '''
        mat = np.eye(3) # 3x3の単位行列
        mat[0, 2] = float(offset_x)
        mat[1, 2] = float(offset_y)

        self.mat_affine = np.dot(mat, self.mat_affine)

    def scale(self, scale:float):
        ''' 拡大縮小 '''
        mat = np.eye(3) # 単位行列
        mat[0, 0] = scale
        mat[1, 1] = scale

        self.mat_affine = np.dot(mat, self.mat_affine)

    def scale_at(self, scale:float, cx:float, cy:float):
        ''' 座標(cx, cy)を中心に拡大縮小 '''

        # 原点へ移動
        self.translate(-cx, -cy)
        # 拡大縮小
        self.scale(scale)
        # 元に戻す
        self.translate(cx, cy)

    def zoom_fit(self, image_width, image_height):
        '''画像をウィジェット全体に表示させる'''

        # キャンバスのサイズ
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if (image_width * image_height <= 0) or (canvas_width * canvas_height <= 0):
            return

        # アフィン変換の初期化
        self.reset_transform()

        scale = 1.0
        offsetx = 0.0
        offsety = 0.0

        if (canvas_width * image_height) > (image_width * canvas_height):
            # ウィジェットが横長（画像を縦に合わせる）
            scale = canvas_height / image_height
            # あまり部分の半分を中央に寄せる
            offsetx = (canvas_width - image_width * scale) / 2
        else:
            # ウィジェットが縦長（画像を横に合わせる）
            scale = canvas_width / image_width
            # あまり部分の半分を中央に寄せる
            offsety = (canvas_height - image_height * scale) / 2

        # 拡大縮小
        self.scale(scale)
        # あまり部分を中央に寄せる
        self.translate(offsetx, offsety)

    # -------------------------------------------------------------------------------
    # 描画
    # -------------------------------------------------------------------------------

    def draw_image(self, cv_image):

        if cv_image is None:
            return
        self.re_image = cv_image.copy()#四角形描画用
        self.cv_image = cv_image        #オーバーレイ用のコピー

        # 位置選択表示
        disp_point_buf = []
        disp_point_flag = 0

        if len(self.point_data) > 1:
            for i in range(int(len(self.point_data)-1)):
                if self.line_indexlist[i] == self.line_indexlist[i+1]:
                    disp_point_buf.append(self.point_data[i][:])
                    disp_point_flag = 0
                else:
                    disp_point_buf.append(self.point_data[i][:])
                    disp_point = np.array(disp_point_buf)
                    disp_point_buf = []
                    disp_point_flag = 1
                    cv2.polylines(self.re_image, [disp_point], False, (0, 0, 255),1)

            if disp_point_flag == 0:
                if self.line_indexlist[-2] == self.line_indexlist[-1]:
                    disp_point_buf.append(self.point_data[-1][:])
                    disp_point = np.array(disp_point_buf)
                    cv2.polylines(self.re_image, [disp_point], False, (0, 0, 255),1)

        if len(self.point_data) > 0:
            disp_point = np.array(self.point_data)
            for j in range(len(disp_point)):
                if self.vpoint_indexlist[j] == self.vpoint_index:
                    cv2.drawMarker(self.re_image, disp_point[j,:], (255, 0, 0))
                else:
                    cv2.drawMarker(self.re_image, disp_point[j,:], (100, 100, 100))

            self.undis_point = []
            for i in range(max(self.line_indexlist)+1):
                N = []
                for j in range(len(self.point_data)):
                    if self.line_indexlist[j] == i:
                        N.append([self.point_data[j][0],self.point_data[j][1],1])
                N = np.array(N)
                Nd = self.calc_distortion(N,self.params)
                self.undis_point = self.undis_point+Nd[:,0:2].tolist()

            disp_point = np.array(self.undis_point)
            for j in range(len(disp_point)):
                if self.vpoint_indexlist[j] == self.vpoint_index:
                    cv2.drawMarker(self.re_image, disp_point[j,:], (0, 255, 0))
                else:
                    cv2.drawMarker(self.re_image, disp_point[j,:], (100, 150, 100))
                # cv2.drawMarker(self.re_image, disp_point[j,:], (0, 255, 0))

        if self.undistort_view == 1:
            for i in range(len(self.vpoint_data)):
                cv2.circle(self.re_image, [int(self.vpoint_data[i,0]),int(self.vpoint_data[i,1])], 5, (0, 255, 0), thickness=-1)
        

        self.canvas.delete("all")

        # キャンバスのサイズ
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        # キャンバスから画像データへのアフィン変換行列を求める
        #（表示用アフィン変換行列の逆行列を求める）
        mat_inv = np.linalg.inv(self.mat_affine)

        # ndarray(OpenCV)からPillowへ変換
        # カラー画像のときは、BGRからRGBへ変換する
        if self.re_image.ndim == 3:
            self.re_image = cv2.cvtColor(self.re_image, cv2.COLOR_BGR2RGB)
        # NumPyからPillowへ変換
        self.pil_image = Image.fromarray(self.re_image)

        # PILの画像データをアフィン変換する
        dst = self.pil_image.transform(
                    (canvas_width, canvas_height),  # 出力サイズ
                    Image.Transform.AFFINE,         # アフィン変換
                    tuple(mat_inv.flatten()),       # アフィン変換行列（出力→入力への変換行列）を一次元のタプルへ変換
                    Image.Resampling.NEAREST,       # 補間方法、ニアレストネイバー
                    fillcolor= self.back_color
                    )

        # 表示用画像を保持
        self.image = ImageTk.PhotoImage(image=dst)

        # 画像の描画
        self.canvas.create_image(
                0, 0,               # 画像表示位置(左上の座標)
                anchor='nw',        # アンカー、左上が原点
                image=self.image    # 表示画像データ
                )

    def redraw_image(self):
        ''' 画像の再描画 '''
        if self.cv_image is None:
            return
        self.draw_image(self.cv_image)

    # -------------------------------------------------------------------------------
    # ボタンイベント（画像処理）
    # -------------------------------------------------------------------------------
    def btn_lineback_click(self):
        if self.vpoint_index < 1:
            return
        self.vpoint_index = self.vpoint_index - 1
        self.lbl_linenum["text"] = str(self.vpoint_index)

        cnt = 0
        for i in range(len(self.vpoint_indexlist)):
            if self.vpoint_indexlist[i] == self.vpoint_index:
                cnt = cnt + 1
        if cnt < 2:
            self.btn_linenext["state"] = tk.DISABLED
        else:
            self.btn_linenext["state"] = tk.NORMAL
        self.redraw_image()

    def btn_linenext_click(self):
        self.vpoint_index = self.vpoint_index + 1
        self.lbl_linenum["text"] = str(self.vpoint_index)
        
        cnt = 0
        for i in range(len(self.vpoint_indexlist)):
            if self.vpoint_indexlist[i] == self.vpoint_index:
                cnt = cnt + 1
        if cnt < 2:
            self.btn_linenext["state"] = tk.DISABLED
        else:
            self.btn_linenext["state"] = tk.NORMAL
        self.redraw_image()

    def btn_del_click(self):
        if self.cv_image is None:
            return
        self.point_data = []
        self.line_indexlist = []
        self.vpoint_indexlist = []
        self.line_index = 0
        self.vpoint_index = 0
        self.CTRL_KEY_ON = 0
        self.select_mode = 0
        self.undistort_view = 0
        self.undis_point = []
        self.undist_flg = 0
        self.prog_var.set(0)
        self.redraw_image()

    def btn_cal_click(self):
        if self.cv_image is None:
            return
        if max(self.vpoint_indexlist) < 1:
            return

        self.btn_del["state"] = "disable"
        self.btn_cal["state"] = "disable"
        self.file_menu.entryconfig( 0, state="disable" )
        self.file_menu.entryconfig( 1, state="disable" )


        self.undis_point = []
        for i in range(max(self.line_indexlist)+1):
            N = []
            for j in range(len(self.point_data)):
                if self.line_indexlist[j] == i:
                    N.append([self.point_data[j][0],self.point_data[j][1],1])
            N = np.array(N)
            Nd = self.calc_distortion(N,self.params)
            self.undis_point = self.undis_point+Nd[:,0:2].tolist()
            A = np.vstack([Nd[:,0],np.ones(len(Nd))]).T

        f ,self.vpoint_data = self.getIntersection()
        if f == 1:
            self.undistort_view = 1
        else:
            return

        m = np.ones([len(self.vpoint_data),3])
        for i in range(len(m)):
            m[i,0] = self.vpoint_data[i,0]
            m[i,1] = self.vpoint_data[i,1]
        all = itertools.combinations(range(len(m)), 2)


        vangle = self.tb_vangle.get()
        try:
            float(vangle)  # 文字列を実際にfloat関数で変換してみる
        except ValueError:
            f_vangle = 90.0/180*np.pi
            self.tb_vangle.delete(0, tk.END)
            self.tb_vangle.insert(tk.END,"90.0")
        else:
            if 0 > float(vangle):
                f_vangle = 1.0/180*np.pi
                self.tb_vangle.delete(0, tk.END)
                self.tb_vangle.insert(tk.END,"1.0")
            elif 90.0 < float(vangle):
                f_vangle = 90.0/180*np.pi
                self.tb_vangle.delete(0, tk.END)
                self.tb_vangle.insert(tk.END,"90.0")
            else:
                f_vangle = float(vangle)/180*np.pi
        for x in all:
            m1 = m[x[0],:].T
            m2 = m[x[1],:].T
            theta = f_vangle
            Ax = m1[0]-self.params[0]
            Ay = m1[1]-self.params[1]
            Bx = m2[0]-self.params[0]
            By = m2[1]-self.params[1]

            f_calc2m = (-Ax**2*np.cos(theta)**2 + 2*Ax*Bx - Ay**2*np.cos(theta)**2 + 2*Ay*By - Bx**2*np.cos(theta)**2 - By**2*np.cos(theta)**2 - np.sqrt(np.cos(theta)**2*(Ax**4*np.cos(theta)**2 - 4*Ax**3*Bx + 2*Ax**2*Ay**2*np.cos(theta)**2 - 4*Ax**2*Ay*By - 2*Ax**2*Bx**2*np.cos(theta)**2 + 8*Ax**2*Bx**2 - 2*Ax**2*By**2*np.cos(theta)**2 + 4*Ax**2*By**2 - 4*Ax*Ay**2*Bx + 8*Ax*Ay*Bx*By - 4*Ax*Bx**3 - 4*Ax*Bx*By**2 + Ay**4*np.cos(theta)**2 - 4*Ay**3*By - 2*Ay**2*Bx**2*np.cos(theta)**2 + 4*Ay**2*Bx**2 - 2*Ay**2*By**2*np.cos(theta)**2 + 8*Ay**2*By**2 - 4*Ay*Bx**2*By - 4*Ay*By**3 + Bx**4*np.cos(theta)**2 + 2*Bx**2*By**2*np.cos(theta)**2 + By**4*np.cos(theta)**2)))/(2*(np.cos(theta)**2 - 1))
            f_calc2p = (-Ax**2*np.cos(theta)**2 + 2*Ax*Bx - Ay**2*np.cos(theta)**2 + 2*Ay*By - Bx**2*np.cos(theta)**2 - By**2*np.cos(theta)**2 + np.sqrt(np.cos(theta)**2*(Ax**4*np.cos(theta)**2 - 4*Ax**3*Bx + 2*Ax**2*Ay**2*np.cos(theta)**2 - 4*Ax**2*Ay*By - 2*Ax**2*Bx**2*np.cos(theta)**2 + 8*Ax**2*Bx**2 - 2*Ax**2*By**2*np.cos(theta)**2 + 4*Ax**2*By**2 - 4*Ax*Ay**2*Bx + 8*Ax*Ay*Bx*By - 4*Ax*Bx**3 - 4*Ax*Bx*By**2 + Ay**4*np.cos(theta)**2 - 4*Ay**3*By - 2*Ay**2*Bx**2*np.cos(theta)**2 + 4*Ay**2*Bx**2 - 2*Ay**2*By**2*np.cos(theta)**2 + 8*Ay**2*By**2 - 4*Ay*Bx**2*By - 4*Ay*By**3 + Bx**4*np.cos(theta)**2 + 2*Bx**2*By**2*np.cos(theta)**2 + By**4*np.cos(theta)**2)))/(2*(np.cos(theta)**2 - 1))

        if f_calc2m > 0:
            self.lbl_focal1["text"] ="推定焦点距離候補1："+ '{:.2f}'.format(np.sqrt(f_calc2m)) + " [pixel]"
        else:
            self.lbl_focal1["text"] ="推定焦点距離候補1："+ "解なし"
        if f_calc2p > 0:
            self.lbl_focal2["text"] ="推定焦点距離候補2："+ '{:.2f}'.format(np.sqrt(f_calc2p)) + " [pixel]"
        else:
            self.lbl_focal2["text"] ="推定焦点距離候補2："+ "解なし"

        self.btn_del["state"] = "active"
        self.btn_cal["state"] = "active"
        self.file_menu.entryconfig(0, state="active" )
        self.file_menu.entryconfig(1, state="active" )
        self.redraw_image()

    def calc_distortion(self,point_data,params):
        cx = params[0]
        cy = params[1]
        k1 = params[2]
        k2 = params[3]
        k3 = params[4]
        k4 = params[5]
        point_data_ans = point_data.copy()
        for i in range(len(point_data)):
            x = point_data[i,0] - cx
            y = point_data[i,1] - cy
            r2 = x**2 + y**2
            f = (1+k1*r2+k2*r2**2)/(1+k3*r2+k4*r2**2)
            point_data_ans[i,0] = x*f + cx
            point_data_ans[i,1] = y*f + cy
        return point_data_ans
    
    def getIntersection(self):
        xy = []
        for j in range(max(self.vpoint_indexlist)+1):
            cnt0 = self.line_indexlist[0]
            pbuf0 = []
            acbuf0 = []
            init_flg = 0
            for i in range(len(self.point_data)):
                if self.vpoint_indexlist[i] == j:
                    if self.line_indexlist[i] == cnt0 or init_flg == 0:
                        pbuf0.append([self.point_data[i][0],self.point_data[i][1],1])
                    else:
                        N = np.array(pbuf0)
                        Nd = self.calc_distortion(N,self.params)
                        A = np.vstack([Nd[:,0],np.ones(len(Nd))]).T
                        A,C = np.linalg.lstsq(A,Nd[:,1],None)[0]
                        acbuf0.append([A,C])              
                        pbuf0 = []
                        pbuf0.append([self.point_data[i][0],self.point_data[i][1],1])
                    cnt0 = self.line_indexlist[i]
                    init_flg = 1
            N = np.array(pbuf0)
            Nd = self.calc_distortion(N,self.params)
            A = np.vstack([Nd[:,0],np.ones(len(Nd))]).T
            A,C = np.linalg.lstsq(A,Nd[:,1],None)[0]
            acbuf0.append([A,C])
            r = 0
            A11 = 0
            A12 = 0
            A21 = 0
            A22 = 0
            B1 = 0
            B2 = 0
            cnt = 0
            for i in range(len(acbuf0)):
                A = -acbuf0[i][0]
                B = 1
                C = acbuf0[i][1]
                r = C/np.sqrt((-A)**2+(B)**2)
                cos_t = np.cos(np.arctan(A))
                sin_t = np.sin(np.arctan(A))
                A11 = A11 + cos_t**2
                A12 = A12 + cos_t*sin_t
                A21 = A21 + cos_t*sin_t
                A22 = A22 + sin_t**2
                B1 = B1 + r*cos_t
                B2 = B2 + r*sin_t
                cnt = cnt + 1
            if cnt > 1:
                A = np.array([[A11,A12],[A21,A22]])
                B = np.array([B1,B2])
                ans = np.linalg.inv(A)@B.T
                ans_in = np.zeros(2)
                ans_in[0] = ans[1]
                ans_in[1] = ans[0]
                xy.append(ans_in)

            else:
                xy.append([0,0])
        xy = np.array(xy)

        for i in range(len(xy)):
            if np.isnan(xy[i,0]) or np.isnan(xy[i,1]):
                return -1 ,xy
        return 1 , xy

if __name__ == "__main__":
    root = tk.Tk()
    app = Application(master=root)
    app.mainloop()
