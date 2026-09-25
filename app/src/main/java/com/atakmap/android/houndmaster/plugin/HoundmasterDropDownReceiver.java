package com.atakmap.android.houndmaster.plugin;

import android.content.Context;
import android.content.Intent;
import com.atakmap.android.dropdown.DropDownReceiver;
import com.atakmap.android.maps.MapView;

public class HoundmasterDropDownReceiver extends DropDownReceiver {
    private final Context pluginContext;
    private final MapView mapView;

    public HoundmasterDropDownReceiver(MapView mapView, Context pluginContext) {
        super(mapView);
        this.pluginContext = pluginContext;
        this.mapView = mapView;
    }

    @Override
    public void onReceive(Context context, Intent intent) {
        // Show the Houndmaster Dashboard when the plugin icon is clicked
        BloodhoundDashboardDropDown dash = new BloodhoundDashboardDropDown(mapView, pluginContext, BloodhoundOrderManager.getInstance());
        dash.show();
    }

    @Override
    protected void disposeImpl() {
        // No special cleanup required
    }
}
