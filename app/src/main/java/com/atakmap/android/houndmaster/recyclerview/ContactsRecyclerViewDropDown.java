package com.atakmap.android.houndmaster.recyclerview;

import android.content.Intent;

import android.content.Context;
import androidx.recyclerview.widget.LinearLayoutManager;
import android.view.LayoutInflater;
import android.view.View;
import com.atakmap.android.dropdown.DropDownReceiver;
import com.atakmap.android.houndmaster.plugin.R;
import com.atakmap.android.maps.MapItem;
import com.atakmap.android.maps.MapView;
import com.atakmap.android.util.time.TimeListener;
import com.atakmap.android.util.time.TimeViewUpdater;

/**
 * Drop-down menu to show only contacts in a RecyclerView, labeled "Contacts"
 */
public class ContactsRecyclerViewDropDown extends DropDownReceiver implements TimeListener {
    private final MapView _mapView;
    private final Context _plugin;
    private final TimeViewUpdater _timeUpdater;
    private final View _view;
    private final RecyclerView _rView;
    private final RecyclerViewAdapter _adapter;
    private final MapItem selectedMapItem;
    private OnContactSelectedListener onContactSelectedListener;

    public ContactsRecyclerViewDropDown(MapView mapView, Context plugin, MapItem selectedMapItem) {
        super(mapView);
        _mapView = mapView;
        _plugin = plugin;
        this.selectedMapItem = selectedMapItem;
        _view = LayoutInflater.from(_plugin).inflate(R.layout.recycler_view, mapView, false);
        _rView = _view.findViewById(R.id.rView);
        _adapter = new RecyclerViewAdapter(_mapView, _plugin, true); // true = contacts only
        _rView.setAdapter(_adapter);
        _rView.setLayoutManager(new LinearLayoutManager(_plugin, LinearLayoutManager.VERTICAL, false));
        // Set label to "Contacts"
        View label = _view.findViewById(R.id.recyclerViewLabel);
        if (label instanceof android.widget.TextView) {
            ((android.widget.TextView) label).setText("Contacts");
        }
        _adapter.setOnItemSelectedListener(new RecyclerViewAdapter.OnItemSelectedListener() {
            @Override
            public void onItemSelected(MapItem contact) {
                if (onContactSelectedListener != null) {
                    onContactSelectedListener.onContactSelected(selectedMapItem, contact);
                }
                dispose();
            }
        });
        _timeUpdater = new TimeViewUpdater(_mapView, 1000);
        _timeUpdater.register(this);
    }

    @Override
    public void disposeImpl() {
        _timeUpdater.unregister(this);
    }

    @Override
    public void onTimeChanged(com.atakmap.coremap.maps.time.CoordinatedTime ot, com.atakmap.coremap.maps.time.CoordinatedTime nt) {
        if (isVisible())
            _adapter.notifyDataSetChanged();
    }

    public View getView() {
        return _view;
    }

    public void show() {
        showDropDown(_view, THREE_EIGHTHS_WIDTH, FULL_HEIGHT, FULL_WIDTH, THIRD_HEIGHT);
    }

    public void onReceive(Context context, Intent intent) {
        // No broadcast handling needed for this drop-down
    }

    public void setOnContactSelectedListener(OnContactSelectedListener listener) {
        this.onContactSelectedListener = listener;
    }

    public interface OnContactSelectedListener {
        void onContactSelected(MapItem mapItem, MapItem contact);
    }
}
