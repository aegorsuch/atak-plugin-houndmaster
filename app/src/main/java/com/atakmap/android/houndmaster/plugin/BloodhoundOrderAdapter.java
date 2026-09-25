package com.atakmap.android.houndmaster.plugin;

import android.app.AlertDialog;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageButton;
import android.widget.TextView;
import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;
import java.util.List;

public class BloodhoundOrderAdapter extends RecyclerView.Adapter<BloodhoundOrderAdapter.OrderViewHolder> {
    public interface OnDeleteClickListener {
        void onDelete(BloodhoundOrder order);
    }
    private final List<BloodhoundOrder> orders;
    private final OnDeleteClickListener deleteClickListener;
    private final android.content.Context dialogContext;
    public BloodhoundOrderAdapter(List<BloodhoundOrder> orders,
            OnDeleteClickListener deleteClickListener, android.content.Context dialogContext) {
        this.orders = orders;
        this.deleteClickListener = deleteClickListener;
        this.dialogContext = dialogContext;
    }
    @NonNull
    @Override
    public OrderViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View v = LayoutInflater.from(parent.getContext()).inflate(R.layout.bloodhound_order_row, parent, false);
        return new OrderViewHolder(v);
    }
    @Override
    public void onBindViewHolder(@NonNull OrderViewHolder holder, int position) {
        BloodhoundOrder order = orders.get(position);
        holder.title.setText(order.getMapItemTitle());
        holder.contact.setText(order.getContact());
        holder.status.setText(order.getStatus() == BloodhoundOrder.Status.Bloodhounding
                ? "Active" : order.getStatus().name());
        holder.deleteBtn.setOnClickListener(v -> new AlertDialog.Builder(dialogContext)
                .setTitle("Delete order")
                .setMessage("Delete this Bloodhound order?")
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Delete", (dialog, which) -> deleteClickListener.onDelete(order))
                .show());
    }
    @Override
    public int getItemCount() {
        return orders.size();
    }
    static class OrderViewHolder extends RecyclerView.ViewHolder {
        TextView title, contact, status;
        ImageButton deleteBtn;
        OrderViewHolder(View v) {
            super(v);
            title = v.findViewById(R.id.orderTitle);
            contact = v.findViewById(R.id.orderContact);
            status = v.findViewById(R.id.orderStatus);
            deleteBtn = v.findViewById(R.id.deleteOrderBtn);
        }
    }
}
