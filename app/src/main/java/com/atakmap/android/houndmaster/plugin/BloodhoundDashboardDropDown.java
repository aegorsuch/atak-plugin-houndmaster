package com.atakmap.android.houndmaster.plugin;

import android.content.Context;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.ImageButton;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import com.atakmap.android.dropdown.DropDownReceiver;
import com.atakmap.android.maps.MapView;

public class BloodhoundDashboardDropDown extends DropDownReceiver {
    private final View _view;
    private final MapView _mapView;
    private final BloodhoundOrderAdapter adapter;
    private final BloodhoundOrderManager orderManager;
    private final BloodhoundOrderManager.OrderChangeListener orderChangeListener;

    public BloodhoundDashboardDropDown(MapView mapView, Context plugin, BloodhoundOrderManager orderManager) {
        super(mapView);
        this._mapView = mapView;
        this.orderManager = orderManager;
        _view = LayoutInflater.from(plugin).inflate(R.layout.bloodhound_dashboard, mapView, false);
        RecyclerView rv = _view.findViewById(R.id.bloodhoundOrdersRecyclerView);
        rv.setLayoutManager(new LinearLayoutManager(plugin));
        adapter = new BloodhoundOrderAdapter(orderManager.getOrders(), orderManager::removeOrder,
                mapView.getContext());
        rv.setAdapter(adapter);
        orderChangeListener = adapter::notifyDataSetChanged;
        orderManager.addOrderChangeListener(orderChangeListener);

        // Set up Add new Bloodhound order button
        ImageButton addOrderButton = _view.findViewById(R.id.addBloodhoundOrderButton);
        addOrderButton.setOnClickListener(v -> {
            // Show the add order flow (show map items for selection)
            com.atakmap.android.houndmaster.recyclerview.RecyclerViewDropDown dropDown = new com.atakmap.android.houndmaster.recyclerview.RecyclerViewDropDown(_mapView, plugin);
            dropDown.show();
        });
    }

    public void show() {
        // Show the dashboard as a drop-down
        showDropDown(_view, HALF_WIDTH, FULL_HEIGHT, FULL_WIDTH, THIRD_HEIGHT);
    }

    public View getView() {
        return _view;
    }

    @Override
    protected void disposeImpl() {
        orderManager.removeOrderChangeListener(orderChangeListener);
    }

    @Override
    public void onReceive(Context context, android.content.Intent intent) {
        // No broadcast handling needed for this drop-down
    }

    public static void showDashboard(MapView mapView, Context plugin) {
        BloodhoundDashboardDropDown dash = new BloodhoundDashboardDropDown(mapView, plugin, BloodhoundOrderManager.getInstance());
        dash.show();
    }
}
