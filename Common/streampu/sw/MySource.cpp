#include <random>
#include "MySource.hpp"

using namespace spu;
using namespace spu::module;

    MySource::MySource(int frame_size, int data_width) : Stateful(), frame_size(frame_size), data_width(data_width) {

        this->set_name("MySource");
        this->set_short_name("MySource");

        auto &t = create_task("generate");
        auto output   = create_socket_out<int>(t, "output", frame_size);

        this->create_codelet(t, [output](Module &m, runtime::Task &t, const size_t frame_id) -> int {
        static_cast<MySource&>(m).generate(  static_cast<int*>(t[output].get_dataptr()),
                                                        frame_id);
        return 0;
    });

    }

    MySource::~MySource() {
    }    

    void MySource::generate(int *output, const int frame_id) {
        
        std::random_device rd;
        // std::mt19937 rand_gen(rd());
        std::mt19937 rand_gen(42);
        std::uniform_int_distribution<> dis(-1*(1<<(data_width-1)), 1<<(data_width-1)-1);

        int i = 0;
        while(i < frame_size)
        {
            output[i++] = dis(rand_gen);
        }        
    }