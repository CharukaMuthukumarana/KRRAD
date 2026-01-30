// monitor/src/xdp_counter.c
#include <uapi/linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/in.h>

// Define a structure to hold both metrics
struct metrics_t {
    u64 packets;
    u64 bytes;
};

// Map: Protocol (u32) -> Metrics (struct metrics_t)
BPF_HASH(metrics_map, u32, struct metrics_t);

// Map for Blacklist
BPF_HASH(blacklist, u32, u8);

int xdp_prog(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    struct ethhdr *eth = data;
    // Bounds check 1
    if ((void *)eth + sizeof(*eth) > data_end)
        return XDP_PASS;

    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return XDP_PASS;

    struct iphdr *ip = data + sizeof(*eth);
    // Bounds check 2
    if ((void *)ip + sizeof(*ip) > data_end)
        return XDP_PASS;

    // --- LOGIC 1: CHECK BLACKLIST ---
    u32 src_ip = ip->saddr;
    u8 *blocked = blacklist.lookup(&src_ip);
    if (blocked) {
        return XDP_DROP;
    }

    // --- LOGIC 2: COUNT ACTUAL BYTES & PACKETS ---
    u32 protocol = ip->protocol;
    
    // Calculate the actual packet length (End - Start)
    u64 packet_len = (u64)(data_end - data);

    // Initialize with 0 if protocol not seen yet
    struct metrics_t zero = {0, 0};
    struct metrics_t *val = metrics_map.lookup_or_try_init(&protocol, &zero);
    
    if (val) {
        // Atomic increment for thread safety
        lock_xadd(&val->packets, 1);
        lock_xadd(&val->bytes, packet_len);
    }

    return XDP_PASS;
}