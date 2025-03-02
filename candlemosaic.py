import os
import sqlite3
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox

import cv2
import numpy as np
from PIL import Image, ImageTk


class CandleMosaicApp:
    def __init__(self, root):
        self.root = root
        self.root.title("キャンドルナイトモザイクアート")
        self.root.geometry("1200x800")

        # データベースの初期化
        self.init_database()

        # 校章画像の読み込み（仮のパス - 実際には実在する校章画像のパスを設定）
        self.logo_path = "school_logo.png"
        self.check_logo_exists()

        # モザイク用のパラメータ
        self.tile_size = 50  # モザイクの各タイルのサイズ
        self.photos = []  # 取り込んだ写真のリスト

        # GUI要素の作成
        self.create_widgets()

        # モザイクアートの更新スレッド
        self.running = True
        self.update_thread = threading.Thread(target=self.auto_update_mosaic)
        self.update_thread.daemon = True
        self.update_thread.start()

    def check_logo_exists(self):
        """校章画像の存在確認と作成"""
        if not os.path.exists(self.logo_path):
            # 校章が存在しない場合、サンプル用の画像を作成
            sample_logo = Image.new('RGB', (500, 500), color='white')
            # 簡単な円形を描画（実際には校章を用意）
            import PIL.ImageDraw as ImageDraw
            draw = ImageDraw.Draw(sample_logo)
            draw.ellipse((100, 100, 400, 400), fill='blue', outline='blue')
            draw.ellipse((150, 150, 350, 350), fill='white', outline='white')
            sample_logo.save(self.logo_path)
            messagebox.showinfo("情報", f"サンプル校章画像を作成しました。実際の校章画像を '{self.logo_path}' として保存してください。")

    def init_database(self):
        """SQLiteデータベースの初期化"""
        self.conn = sqlite3.connect('candle_mosaic.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def create_widgets(self):
        """GUI要素の作成"""
        # メインフレーム
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左側：操作パネル
        control_frame = tk.Frame(main_frame, width=300)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        # 写真取込ボタン
        upload_btn = tk.Button(control_frame, text="写真を取り込む", command=self.upload_photo, height=2)
        upload_btn.pack(fill=tk.X, pady=5)

        # カメラ撮影ボタン
        camera_btn = tk.Button(control_frame, text="カメラで撮影", command=self.take_photo, height=2)
        camera_btn.pack(fill=tk.X, pady=5)

        # モザイク更新ボタン
        update_btn = tk.Button(control_frame, text="モザイクを更新", command=self.update_mosaic, height=2)
        update_btn.pack(fill=tk.X, pady=5)

        # タイルサイズ設定
        size_frame = tk.Frame(control_frame)
        size_frame.pack(fill=tk.X, pady=10)

        tk.Label(size_frame, text="タイルサイズ:").pack(side=tk.LEFT)
        self.tile_slider = tk.Scale(size_frame, from_=20, to=100, orient=tk.HORIZONTAL, command=self.update_tile_size)
        self.tile_slider.set(self.tile_size)
        self.tile_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 写真リスト表示
        tk.Label(control_frame, text="取り込んだ写真:").pack(anchor=tk.W, pady=(15, 5))
        self.photo_listbox = tk.Listbox(control_frame, height=15)
        self.photo_listbox.pack(fill=tk.BOTH, expand=True)

        # 写真削除ボタン
        delete_btn = tk.Button(control_frame, text="選択した写真を削除", command=self.delete_selected_photo)
        delete_btn.pack(fill=tk.X, pady=5)

        # 右側：モザイク表示エリア
        display_frame = tk.Frame(main_frame, bg="black")
        display_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(display_frame, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 撮影履歴の読み込み
        self.load_photos_from_db()

        # 初期モザイク生成
        self.update_mosaic()

    def load_photos_from_db(self):
        """DBから写真を読み込む"""
        self.cursor.execute("SELECT path FROM photos ORDER BY timestamp DESC")
        rows = self.cursor.fetchall()
        self.photos = [row[0] for row in rows if os.path.exists(row[0])]

        # リストボックスの更新
        self.update_photo_listbox()

    def update_photo_listbox(self):
        """写真リストボックスの更新"""
        self.photo_listbox.delete(0, tk.END)
        for idx, path in enumerate(self.photos, 1):
            filename = os.path.basename(path)
            self.photo_listbox.insert(tk.END, f"{idx}: {filename}")

    def upload_photo(self):
        """写真ファイルを選択して取り込む"""
        filetypes = [("画像ファイル", "*.jpg *.jpeg *.png")]
        filepaths = filedialog.askopenfilenames(title="写真を選択", filetypes=filetypes)

        if filepaths:
            for filepath in filepaths:
                # 同じファイルが既に存在するか確認
                if filepath not in self.photos:
                    # DBに追加
                    self.cursor.execute("INSERT INTO photos (path) VALUES (?)", (filepath,))
                    self.conn.commit()

                    # リストに追加
                    self.photos.append(filepath)

            self.update_photo_listbox()
            messagebox.showinfo("写真取込", f"{len(filepaths)}枚の写真を取り込みました。")

            # モザイク更新
            self.update_mosaic()

    def take_photo(self):
        """カメラで撮影する"""
        # カメラキャプチャの初期化
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            messagebox.showerror("エラー", "カメラを開けませんでした。")
            return

        # カメラプレビューウィンドウ
        preview_window = tk.Toplevel(self.root)
        preview_window.title("カメラプレビュー")
        preview_window.geometry("800x600")

        # プレビュー用キャンバス
        preview_canvas = tk.Canvas(preview_window, width=640, height=480)
        preview_canvas.pack(pady=10)

        # 撮影ボタン
        capture_btn = tk.Button(preview_window, text="撮影する", font=("", 12), height=2)
        capture_btn.pack(fill=tk.X, padx=20, pady=10)

        # カメラプレビュー表示用フラグ
        preview_active = True

        def update_preview():
            if preview_active:
                ret, frame = cap.read()
                if ret:
                    # OpenCVの画像をPIL形式に変換
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)
                    img = ImageTk.PhotoImage(image=img)

                    # キャンバスに表示
                    preview_canvas.create_image(0, 0, anchor=tk.NW, image=img)
                    preview_canvas.image = img

                    # 次のフレーム更新をスケジュール
                    preview_window.after(30, update_preview)

        def capture_image():
            nonlocal preview_active
            ret, frame = cap.read()
            if ret:
                # タイムスタンプを使用して一意のファイル名を作成
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if not os.path.exists("captures"):
                    os.makedirs("captures")
                filepath = os.path.join("captures", f"candle_{timestamp}.jpg")

                # 画像を保存
                cv2.imwrite(filepath, frame)

                # DBに追加
                self.cursor.execute("INSERT INTO photos (path) VALUES (?)", (filepath,))
                self.conn.commit()

                # リストに追加
                self.photos.append(filepath)
                self.update_photo_listbox()

                # プレビュー終了
                preview_active = False
                cap.release()
                preview_window.destroy()

                messagebox.showinfo("撮影完了", "写真を撮影し保存しました。")

                # モザイク更新
                self.update_mosaic()

        # 撮影ボタンのコマンドを設定
        capture_btn.config(command=capture_image)

        # プレビュー開始
        update_preview()

        # ウィンドウが閉じられたときのクリーンアップ
        def on_closing():
            nonlocal preview_active
            preview_active = False
            cap.release()
            preview_window.destroy()

        preview_window.protocol("WM_DELETE_WINDOW", on_closing)

    def delete_selected_photo(self):
        """選択した写真を削除"""
        selected_index = self.photo_listbox.curselection()
        if not selected_index:
            messagebox.showinfo("選択エラー", "削除する写真を選択してください。")
            return

        selected_index = selected_index[0]
        if 0 <= selected_index < len(self.photos):
            path = self.photos[selected_index]

            # DBから削除
            self.cursor.execute("DELETE FROM photos WHERE path = ?", (path,))
            self.conn.commit()

            # リストから削除
            self.photos.pop(selected_index)
            self.update_photo_listbox()

            messagebox.showinfo("削除完了", "選択した写真を削除しました。")

            # モザイク更新
            self.update_mosaic()

    def update_tile_size(self, val):
        """タイルサイズの更新"""
        self.tile_size = int(val)
        self.update_mosaic()

    def auto_update_mosaic(self):
        """定期的なモザイク更新（バックグラウンドスレッド）"""
        while self.running:
            # DBから新しい写真があるか確認
            self.cursor.execute("SELECT path FROM photos ORDER BY timestamp DESC")
            rows = self.cursor.fetchall()
            current_photos = [row[0] for row in rows if os.path.exists(row[0])]

            # 新しい写真がある場合は更新
            if len(current_photos) != len(self.photos):
                self.photos = current_photos
                # GUIスレッドで実行
                self.root.after(0, self.update_photo_listbox)
                self.root.after(0, self.update_mosaic)

            time.sleep(5)  # 5秒ごとに確認

    def update_mosaic(self):
        """モザイクアートの更新"""
        if not os.path.exists(self.logo_path):
            messagebox.showerror("エラー", "校章画像が見つかりません。")
            return

        if not self.photos:
            # 写真がない場合は校章をそのまま表示
            logo_img = Image.open(self.logo_path)
            logo_img = ImageTk.PhotoImage(logo_img)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=logo_img)
            self.canvas.image = logo_img
            return

        # 校章画像の読み込み
        logo = cv2.imread(self.logo_path)
        if logo is None:
            messagebox.showerror("エラー", "校章画像を読み込めませんでした。")
            return

        # キャンバスサイズに合わせてリサイズ
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        # キャンバスがまだサイズ設定されていない場合
        if canvas_width <= 1 or canvas_height <= 1:
            canvas_width = 800
            canvas_height = 600

        # アスペクト比を維持してリサイズ
        logo_height, logo_width = logo.shape[:2]
        aspect_ratio = logo_width / logo_height

        if canvas_width / canvas_height > aspect_ratio:
            new_height = canvas_height
            new_width = int(new_height * aspect_ratio)
        else:
            new_width = canvas_width
            new_height = int(new_width / aspect_ratio)

        logo = cv2.resize(logo, (new_width, new_height))

        # グレースケールに変換してエッジを強調（モザイクのベースとして使用）
        logo_gray = cv2.cvtColor(logo, cv2.COLOR_BGR2GRAY)
        logo_edges = cv2.Canny(logo_gray, 50, 150)

        # モザイクグリッドの計算
        grid_h = new_height // self.tile_size
        grid_w = new_width // self.tile_size

        # 調整されたタイルサイズ
        tile_h = new_height // grid_h
        tile_w = new_width // grid_w

        # 最終的なモザイクサイズ
        mosaic_width = tile_w * grid_w
        mosaic_height = tile_h * grid_h

        # 結果画像の初期化
        mosaic = np.zeros((mosaic_height, mosaic_width, 3), dtype=np.uint8)

        # 写真のプリロード
        photo_images = []
        for path in self.photos:
            try:
                img = cv2.imread(path)
                if img is not None:
                    # タイルサイズにリサイズ
                    img = cv2.resize(img, (tile_w, tile_h))
                    photo_images.append(img)
            except Exception as e:
                print(f"画像読み込みエラー {path}: {e}")

        if not photo_images:
            messagebox.showerror("エラー", "有効な写真がありません。")
            return

        # モザイク作成
        photo_idx = 0
        for y in range(grid_h):
            for x in range(grid_w):
                # 現在のタイル位置
                start_y = y * tile_h
                start_x = x * tile_w

                # 校章のエッジ部分かどうかをチェック
                roi = logo_edges[start_y:start_y+tile_h, start_x:start_x+tile_w]
                edge_density = np.sum(roi) / 255 / (tile_h * tile_w)

                if edge_density > 0.01:  # エッジが多い部分には写真を配置
                    # 写真を循環使用
                    img = photo_images[photo_idx % len(photo_images)]
                    photo_idx += 1

                    # ブレンド比率（エッジ密度に基づく）
                    alpha = min(1.0, edge_density * 3)
                    beta = 1.0 - alpha

                    # 校章の対応部分
                    logo_roi = logo[start_y:start_y+tile_h, start_x:start_x+tile_w]

                    # 写真と校章をブレンド
                    blended = cv2.addWeighted(img, alpha, logo_roi, beta, 0)
                    mosaic[start_y:start_y+tile_h, start_x:start_x+tile_w] = blended
                else:
                    # エッジが少ない部分には校章をそのまま使用
                    mosaic[start_y:start_y+tile_h, start_x:start_x+tile_w] = logo[start_y:start_y+tile_h, start_x:start_x+tile_w]

        # OpenCV画像をPIL形式に変換して表示
        mosaic_rgb = cv2.cvtColor(mosaic, cv2.COLOR_BGR2RGB)
        mosaic_img = Image.fromarray(mosaic_rgb)
        mosaic_img = ImageTk.PhotoImage(mosaic_img)

        # キャンバスに表示
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=mosaic_img)
        self.canvas.image = mosaic_img  # 参照を保持

    def on_closing(self):
        """アプリケーション終了時の処理"""
        self.running = False
        if self.conn:
            self.conn.close()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = CandleMosaicApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
