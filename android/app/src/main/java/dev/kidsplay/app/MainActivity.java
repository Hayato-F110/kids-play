package dev.kidsplay.app;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Web の画面から呼べる入口は、ここで登録したものだけ。super.onCreate より前に登録する決まり
        registerPlugin(PictureSaverPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
