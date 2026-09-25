package com.atakmap.android.houndmaster.plugin;

import android.content.Context;
import com.atak.plugins.impl.AbstractPluginTool;
import com.atakmap.android.maps.MapView;
import com.atakmap.android.houndmaster.plugin.R;

public class HoundmasterTool extends AbstractPluginTool {
    public static final String SHOW_HOUNDMASTER = "com.atakmap.android.houndmaster.SHOW_HOUNDMASTER";

    public HoundmasterTool(final Context context) {
        super(context,
                context.getString(R.string.app_name),
                context.getString(R.string.app_name),
                context.getResources().getDrawable(R.drawable.ic_launcher),
                SHOW_HOUNDMASTER);
    }
}

