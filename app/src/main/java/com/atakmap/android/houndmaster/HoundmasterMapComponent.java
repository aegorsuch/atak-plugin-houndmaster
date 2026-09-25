package com.atakmap.android.houndmaster;

import android.content.Context;
import android.content.Intent;
import android.util.Log;

import com.atakmap.android.chat.ChatManagerMapComponent;
import com.atakmap.android.dropdown.DropDownMapComponent;
import com.atakmap.android.houndmaster.plugin.BloodhoundOrderManager;
import com.atakmap.android.houndmaster.plugin.HoundmasterDropDownReceiver;
import com.atakmap.android.houndmaster.plugin.HoundmasterTool;
import com.atakmap.android.ipc.AtakBroadcast.DocumentedIntentFilter;
import com.atakmap.android.maps.MapView;

public class HoundmasterMapComponent extends DropDownMapComponent {
    private static final String TAG = "HoundmasterMapComponent";

    private final BloodhoundOrderManager orderManager =
            BloodhoundOrderManager.getInstance();

    @Override
    public void onCreate(Context context, Intent intent, MapView view) {
        super.onCreate(context, intent, view);
        ChatManagerMapComponent.getInstance().addChatMessageListener(orderManager);

        HoundmasterDropDownReceiver receiver =
                new HoundmasterDropDownReceiver(view, context);
        DocumentedIntentFilter filter = new DocumentedIntentFilter();
        filter.addAction(HoundmasterTool.SHOW_HOUNDMASTER,
                "Show the Houndmaster dashboard");
        registerDropDownReceiver(receiver, filter);
        Log.d(TAG, "Houndmaster dashboard initialized");
    }

    @Override
    protected void onDestroyImpl(Context context, MapView view) {
        ChatManagerMapComponent.getInstance().removeChatMessageListener(orderManager);
        super.onDestroyImpl(context, view);
    }
}
