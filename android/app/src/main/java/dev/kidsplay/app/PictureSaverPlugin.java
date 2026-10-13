package dev.kidsplay.app;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.io.IOException;
import java.io.OutputStream;
import java.util.regex.Pattern;

/**
 * おえかきの絵（PNG）を、端末の「ピクチャ」フォルダに保存する。
 *
 * WebView は、ブラウザと違ってダウンロードを受け取らない。そのため、Web の画面から呼べる入口を
 * 1つだけ作る。通信はしない。権限も要らない（Android 10 以上は、自分が作る画像を権限なしで保存できる）。
 */
@CapacitorPlugin(name = "PictureSaver")
public class PictureSaverPlugin extends Plugin {

    // Web 側が作る名前（日時だけ）と同じ形だけを受け付ける。保存先を変える文字（/ や ..）を通さないため
    private static final Pattern FILE_NAME = Pattern.compile("^oekaki-\\d{8}-\\d{6}\\.png$");
    // 画面いっぱいの絵でも数MBに収まる。それを大きく超えるデータは、絵ではないとみなして断る
    private static final int MAX_BASE64_CHARS = 16 * 1024 * 1024;
    private static final byte[] PNG_SIGNATURE = { (byte) 0x89, 'P', 'N', 'G', '\r', '\n', 0x1A, '\n' };
    private static final String FOLDER = Environment.DIRECTORY_PICTURES + "/AsobiLand";

    /** この端末で保存できるか。できない端末では、Web 側が「ほぞん」ボタンを出さない。 */
    @PluginMethod
    public void canSave(PluginCall call) {
        JSObject result = new JSObject();
        result.put("value", Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q);
        call.resolve(result);
    }

    @PluginMethod
    public void savePng(PluginCall call) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            call.reject("unsupported");
            return;
        }
        String fileName = call.getString("fileName");
        String data = call.getString("data");
        if (fileName == null || !FILE_NAME.matcher(fileName).matches()) {
            call.reject("bad file name");
            return;
        }
        if (data == null || data.length() > MAX_BASE64_CHARS) {
            call.reject("bad data");
            return;
        }
        byte[] bytes;
        try {
            bytes = Base64.decode(data, Base64.DEFAULT);
        } catch (IllegalArgumentException e) {
            call.reject("bad data");
            return;
        }
        if (!isPng(bytes)) {
            call.reject("not png");
            return;
        }

        ContentResolver resolver = getContext().getContentResolver();
        ContentValues values = new ContentValues();
        values.put(MediaStore.Images.Media.DISPLAY_NAME, fileName);
        values.put(MediaStore.Images.Media.MIME_TYPE, "image/png");
        values.put(MediaStore.Images.Media.RELATIVE_PATH, FOLDER);
        // 書き終わるまで、ほかのアプリ（写真アプリなど）から見えないようにする
        values.put(MediaStore.Images.Media.IS_PENDING, 1);

        Uri collection = MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
        Uri item = resolver.insert(collection, values);
        if (item == null) {
            call.reject("cannot create");
            return;
        }
        try (OutputStream out = resolver.openOutputStream(item)) {
            if (out == null) {
                throw new IOException("no stream");
            }
            out.write(bytes);
        } catch (IOException e) {
            // 書きかけのファイルを残さない
            resolver.delete(item, null, null);
            call.reject("cannot write");
            return;
        }
        values.clear();
        values.put(MediaStore.Images.Media.IS_PENDING, 0);
        resolver.update(item, values, null, null);
        call.resolve();
    }

    private static boolean isPng(byte[] bytes) {
        if (bytes.length < PNG_SIGNATURE.length) {
            return false;
        }
        for (int i = 0; i < PNG_SIGNATURE.length; i++) {
            if (bytes[i] != PNG_SIGNATURE[i]) {
                return false;
            }
        }
        return true;
    }
}
